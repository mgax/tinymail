from monocle import _o
from asynch import AsynchJob, start_worker
from imap_worker import ImapWorker

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
    def __init__(self, folder, msg_id, headers):
        self.folder = folder
        self.msg_id = msg_id

def get_worker():
    return start_worker(ImapWorker())

class AccountUpdateJob(AsynchJob):
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

        for name in mailbox_names:
            yield self.update_folder(worker, self.account._folders[name])

        yield worker.disconnect()

    @_o
    def update_folder(self, worker, folder):
        message_ids = yield worker.get_messages_in_folder(folder.name)
        new_message_ids = set(message_ids) - set(folder._messages)
        for msg_id in new_message_ids:
            yield self.fetch_message_headers(worker, folder, msg_id)

    @_o
    def fetch_message_headers(self, worker, folder, msg_id):
        headers = yield worker.get_message_headers(folder.name, msg_id)
        folder._messages[msg_id] = Message(folder, msg_id, headers)
