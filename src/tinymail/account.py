import logging
from monocle import _o
from blinker import signal
from async import AsyncJob, start_worker
from imap_worker import ImapWorker

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

_signals = [signal(name) for name in
            ('account-updated', 'folder-updated', 'message-updated')]

class Account(object):
    def __init__(self, config, db):
        self.name = "The Account"
        self.config = config
        self._db = db
        self._folders = {}
        self._load_from_db()

    def get_imap_config(self):
        return dict( (k, self.config[k]) for k in
                     ('host', 'login_name', 'login_pass') )

    def list_folders(self):
        return self._folders.itervalues()

    def get_folder(self, name):
        return self._folders[name]

    def _load_from_db(self):
        # TODO move this into an async job?
        db_account = self._db.get_account('the-account')
        for db_folder in db_account.list_folders():
            name = db_folder.name
            self._folders[name] = Folder(self, name)

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
    def __init__(self, folder, msg_uid, flags, raw_headers):
        self.folder = folder
        self.msg_uid = msg_uid
        self.flags = flags
        self.raw_headers = raw_headers
        self.raw_full = None

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
        log.debug("Begin update of account %r", self.account.name)
        worker = get_worker()
        yield worker.connect(**self.account.get_imap_config())
        mailbox_names = yield worker.get_mailbox_names()

        new_mailbox_names = set(mailbox_names) - set(self.account._folders)
        if new_mailbox_names:
            db = self.account._db
            db_account = db.get_account('the-account')
            with db.transaction():
                for name in new_mailbox_names:
                    db_account.add_folder(name)
                    self.account._folders[name] = Folder(self.account, name)

        # TODO what happens with folders removed on server?

        signal('account-updated').send(self.account)

        for name in mailbox_names:
            yield self.update_folder(worker, self.account._folders[name])

        yield worker.disconnect()
        log.info("Update finished for account %r", self.account.name)

    @_o
    def update_folder(self, worker, folder):
        log.debug("Updating folder %r", folder.name)
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
            for msg_index, msg_raw_headers in headers_by_index.iteritems():
                msg_uid = index_to_uuid[msg_index]
                msg_flags = message_data[msg_uid]['flags']
                folder._messages[msg_uid] = Message(folder, msg_uid,
                                                    msg_flags, msg_raw_headers)

            signal('folder-updated').send(folder)

        log.info("Finished updating folder %r: %d messages (%d new)",
                 folder.name, len(message_data), len(new_indices))

class MessageLoadFullJob(AsyncJob):
    def __init__(self, message):
        self.message = message

    @_o
    def do_stuff(self):
        message = self.message
        log.debug("Loading full message %r in folder %r",
                 message.msg_uid, message.folder.name)
        worker = get_worker()
        config = dict( (k, message.folder.account.config[k]) for k in
                       ('host', 'login_name', 'login_pass') )
        yield worker.connect(**config)

        mbox_status, message_data = yield worker.get_messages_in_folder(message.folder.name)
        uuid_to_index = {}
        for msg_uid, msg_info in message_data.iteritems():
            msg_index = msg_info['index']
            uuid_to_index[msg_uid] = msg_index

        body = yield worker.get_message_body(uuid_to_index[message.msg_uid])
        message.raw_full = body

        signal('message-updated').send(message)
