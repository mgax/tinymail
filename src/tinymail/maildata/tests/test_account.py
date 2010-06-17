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

class TestMailbox(object):
    def __init__(self, called):
        self.called = called
        self.status = {'UIDNEXT': 13, 'UIDVALIDITY': 22, 'MESSAGES': 1}
        self.uid_to_num = {6: 1}
        self.flags_by_uid = {6: ('\\Seen',)}

    def __enter__(self):
        self.called('__enter__')
        return self

    def __exit__(self, *args):
        self.called('__exit__')

    def message_headers(self, message_uids):
        self.called('message_headers %r' % sorted(message_uids))
        assert message_uids == set([6])
        return {6: 'From: person@example.com\r\n\r\n'}

    def full_message(self, message_uid):
        self.called('full_message')
        assert message_uid == 6
        return ('From: person@example.com\r\n\r\n'
                'hello world!')

class TestServer(object):
    _mailbox_cls = TestMailbox
    def __init__(self, called):
        self.called = called

    def get_mailboxes(self):
        self.called('get_mailboxes')
        return ['folder one', 'folder two']

    def mailbox(self, imap_name):
        assert imap_name == 'folder one'
        return TestMailbox(self.called)

class TestAccount(Account):
    def _configure(self, config):
        (self.remote_do, self.remote_cleanup) = config

    def sync_folders(self):
        pass

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
                op.is_queued(self.reg)
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

    def test_messages_in_folder(self):
        self.account.update_if_needed()
        self._run_loop()
        folder_one = self.account.folders[0]
        self.assertEqual(folder_one.messages, {})
        self.called[:] = []

        folder_one.update_if_needed()
        self._run_loop()
        self.assertEqual(self.called, ['__enter__', '__exit__',
                '__enter__', 'message_headers [6]', '__exit__'])
        self.assertEqual(len(folder_one.messages), 1)

    def test_message(self):
        self.account.update_if_needed()
        self._run_loop()
        folder_one = self.account.folders[0]
        folder_one.update_if_needed()
        self._run_loop()
        message = folder_one.messages[6]
        self.assertEqual(dict(message.headers), {'From': 'person@example.com'})
        self.called[:] = []

        message.request_fullmsg()
        self._run_loop()
        self.assertEqual(self.called, ['__enter__', 'full_message',
                                       '__exit__'])

    def test_events(self):
        events = []
        def event_logger(name):
            return lambda **kwargs: events.append( (name, kwargs) )

        self.reg.subscribe((self.account, 'folders_updated'),
                           event_logger('folders updated'))
        self.account.update_if_needed()
        self._run_loop()
        self.assertEqual(events,
                         [('folders updated', {'account': self.account})])
        events[:] = []

        folder_one = self.account.folders[0]
        self.reg.subscribe((folder_one, 'messages_updated'),
                           event_logger('messages updated'))
        folder_one.update_if_needed()
        self._run_loop()
        self.assertEqual(events,
                         [('messages updated', {'folder': folder_one}),
                          ('messages updated', {'folder': folder_one})])
        events[:] = []

        message = folder_one.messages[6]
        self.reg.subscribe((message, 'full_message'),
                           event_logger('full message'))
        message.request_fullmsg()
        self._run_loop()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0][0], 'full message')
        self.assertTrue(events[0][1]['message'] is message)
        mime = events[0][1]['mime']
        self.assertEqual(mime['From'], 'person@example.com')
        self.assertEqual(mime.get_payload(), 'hello world!')
        events[:] = []
