import unittest

from tinymail.maildata import imapserver
from tinymail.maildata.account import Account
from tinymail.maildata.folder import Folder
from tinymail.maildata.events import Registry
from tinymail.maildata import async

_orig_main_thread = async.main_thread
def mock_main_thread(store):
    def main_thread(func, *args, **kwargs):
        store(lambda: func(*args, **kwargs))
    async.main_thread = main_thread
def restore_main_thread():
    async.main_thread = _orig_main_thread

class TestServer(object):
    def __init__(self, called):
        self.called = called

    def get_mailboxes(self):
        self.called('get_mailboxes')
        return ['folder one', 'folder two']

class TestAccount(Account):
    def _configure(self, config):
        (self.remote_do, self.remote_cleanup) = config

class AccountTest(unittest.TestCase):
    def setUp(self):
        self.reg = Registry()
        self.called = []

        self.op_queue = []
        def remote_cleanup():
            self.called.append('remote_cleanup')
        self.account = TestAccount(self.reg, (self.op_queue.append,
                                              remote_cleanup))

        self.server = TestServer(self.called.append)

        self.mainthread_queue = []
        mock_main_thread(self.mainthread_queue.append)

    def tearDown(self):
        restore_main_thread()

    def _run_loop(self):
        while True:
            if self.op_queue:
                op = self.op_queue.pop()
                op(self.server)
            elif self.mainthread_queue:
                callback = self.mainthread_queue.pop()
                callback()
            else:
                break

    def test_list_folders(self):
        self.assertEqual(self.account.folders, [])
        self.account.update_if_needed()
        self._run_loop()

        self.assertEqual(self.called, ['get_mailboxes'])
        self.assertEqual(len(self.account.folders), 2)
        folder_one = self.account.folders[0]
        self.assertTrue(isinstance(folder_one, Folder))
        self.assertEqual(folder_one.imap_name, 'folder one')
