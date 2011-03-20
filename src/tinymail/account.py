import email
from monocle import _o
from blinker import signal
from async import AsyncJob, start_worker
from imap_worker import ImapWorker

_signals = [signal(name) for name in
            ('account-updated', 'folder-updated', 'message-updated')]

class Account(object):
    def __init__(self, config):
        self.config = config
        self._folders = {}

    def get_imap_config(self):
        return dict( (k, self.config[k]) for k in
                     ('host', 'login_name', 'login_pass') )

    def list_folders(self):
        return self._folders.itervalues()

    def get_folder(self, name):
        return self._folders[name]

    def perform_update(self):
        job = AccountUpdateJob(self)
        job.start()
        assert job.failure is None

class Folder(object):
    def __init__(self, account, name):
        self.account = account
        self.name = name
        self._messages = {}

    def list_messages(self):
        return self._messages.itervalues()

class Message(object):
    def __init__(self, folder, msg_id, flags, headers):
        self.folder = folder
        self.msg_id = msg_id
        self.flags = flags
        self.headers = headers
        self.full = None

    def load_full(self):
        job = MessageLoadFullJob(self)
        job.start()
        assert job.failure is None

def get_worker():
    return start_worker(ImapWorker())

class AccountUpdateJob(AsyncJob):
    def __init__(self, account):
        self.account = account

    @_o
    def do_stuff(self):
        worker = get_worker()
        yield worker.connect(**self.account.get_imap_config())
        mailbox_names = yield worker.get_mailbox_names()
        for name in mailbox_names:
            if name not in self.account._folders:
                self.account._folders[name] = Folder(self.account, name)

        signal('account-updated').send(self.account)

        for name in mailbox_names:
            yield self.update_folder(worker, self.account._folders[name])

        yield worker.disconnect()

    @_o
    def update_folder(self, worker, folder):
        mbox_status, message_data = yield worker.get_messages_in_folder(folder.name)
        new_message_ids = set(message_data) - set(folder._messages)

        new_indices = set()
        index_to_uuid = {}
        for msg_uid, msg_info in message_data.iteritems():
            msg_index = msg_info['index']
            new_indices.add(msg_index)
            index_to_uuid[msg_index] = msg_uid

        if new_indices:
            headers_by_index = yield worker.get_message_headers(new_indices)
            for msg_index, msg_headers_src in headers_by_index.iteritems():
                msg_uid = index_to_uuid[msg_index]
                msg_flags = message_data[msg_uid]['flags']
                msg_headers = email.message_from_string(msg_headers_src)
                folder._messages[msg_uid] = Message(folder, msg_uid,
                                                    msg_flags, msg_headers)

            signal('folder-updated').send(folder)

class MessageLoadFullJob(AsyncJob):
    def __init__(self, message):
        self.message = message

    @_o
    def do_stuff(self):
        worker = get_worker()
        config = dict( (k, self.message.folder.account.config[k]) for k in
                       ('host', 'login_name', 'login_pass') )
        yield worker.connect(**config)

        mbox_status, message_data = yield worker.get_messages_in_folder(self.message.folder.name)
        uuid_to_index = {}
        for msg_uid, msg_info in message_data.iteritems():
            msg_index = msg_info['index']
            uuid_to_index[msg_uid] = msg_index

        body = yield worker.get_message_body(uuid_to_index[self.message.msg_id])
        self.message.full = email.message_from_string(body)

        signal('message-updated').send(self.message)
