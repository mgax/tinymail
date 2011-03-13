from monocle import _o
from asynch import AsynchJob

class Account(object):
    def __init__(self):
        self._folders = {}

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

def get_worker():
    pass

class AccountUpdateJob(AsynchJob):
    def __init__(self, account):
        self.account = account

    @_o
    def do_stuff(self):
        worker = yield get_worker()
        mailbox_names = yield worker.get_mailbox_names()
        for name in mailbox_names:
            if name not in self.account._folders:
                self.account._folders[name] = Folder(self.account, name)
