from mock import Mock, patch
import unittest2 as unittest
from contextlib import contextmanager
from monocle.callback import defer
from blinker import signal

def account_for_test(config=None, db=None):
    from tinymail.account import Account
    if config is None:
        config = {
            'host': 'test_host',
            'login_name': 'test_username',
            'login_pass': 'test_password',
        }
    if db is None:
        db = Mock()
    return Account(config, db)

class AccountTest(unittest.TestCase):
    def test_list_folders(self):
        account = account_for_test()
        fol1, fol2 = Mock(), Mock()
        account._folders = {'fol1': fol1, 'fol2': fol2}

        folders = list(account.list_folders())

        self.assertEqual(folders, [fol1, fol2])

    def test_get_folder(self):
        account = account_for_test()
        fol1, fol2 = Mock(), Mock()
        account._folders = {'fol1': fol1, 'fol2': fol2}

        ret_fol1 = account.get_folder('fol1')

        self.assertTrue(ret_fol1 is fol1)

class FolderTest(unittest.TestCase):
    def test_list_messages(self):
        from tinymail.account import Folder
        folder = Folder(Mock(), 'fol1')
        msg1, msg2 = Mock(), Mock()
        folder._messages = {1: msg1, 2: msg2}

        messages = list(folder.list_messages())

        self.assertEqual(messages, [msg1, msg2])

@contextmanager
def mock_worker(**folders):
    from tinymail.imap_worker import ImapWorker
    worker = Mock(spec=ImapWorker)
    state = {}

    messages_in_folder = {}
    message_headers_in_folder = {}
    for name in folders:
        messages = {}
        message_headers = {}
        for i, (msg_uid, msg_spec) in enumerate(folders[name].iteritems()):
            messages[msg_uid] = {'index': i, 'flags': ()}
            message_headers[i] = "PLACEHOLDER HEADER"
        messages_in_folder[name] = messages
        message_headers_in_folder[name] = message_headers

    worker.connect.return_value = defer(None)

    worker.get_mailbox_names.return_value = defer(list(folders))

    def get_messages_in_folder(name):
        state['name'] = name
        return defer([{}, messages_in_folder[name]])
    worker.get_messages_in_folder.side_effect = get_messages_in_folder

    def get_message_headers(indices):
        name = state['name']
        message_headers = {}
        for i in indices:
            message_headers[i] = message_headers_in_folder[name][i]
        return defer(message_headers)
    worker.get_message_headers.side_effect = get_message_headers

    worker.disconnect.return_value = defer(None)

    with patch('tinymail.account.get_worker', Mock(return_value=worker)):
        yield worker

class AccountUpdateTest(unittest.TestCase):

    def test_list_folders(self):
        account = account_for_test()
        folders = {'fol1': {}, 'fol2': {}}

        with mock_worker(**folders):
            signal_log = []
            with signal('account-updated').connected_to(signal_log.append):
                account.perform_update()

        self.assertEqual(set(f.name for f in account.list_folders()),
                         set(folders))
        self.assertEqual(signal_log, [account])

    def test_list_messages(self):
        account = account_for_test()

        with mock_worker(fol1={6: None, 8: None}):
            signal_log = []
            with signal('folder-updated').connected_to(signal_log.append):
                account.perform_update()

        fol1 = account.get_folder('fol1')
        self.assertEqual(set(m.msg_uid for m in fol1.list_messages()),
                         set([6, 8]))
        self.assertEqual(signal_log, [fol1])

    def test_empty_folder(self):
        account = account_for_test()

        with mock_worker(fol1={}) as worker:
            signal_log = []
            account.perform_update()

        self.assertFalse(worker.get_message_headers.called)

    def test_load_full_message(self):
        account = account_for_test()
        mime_message = "Subject: hi\r\n\r\nHello world!"

        with mock_worker(fol1={6: None}) as worker:
            account.perform_update()
            message = account.get_folder('fol1')._messages[6]
            worker.get_message_body.return_value = defer(mime_message)
            signal_log = []
            with signal('message-updated').connected_to(signal_log.append):
                message.load_full()

        self.assertEqual(message.raw_full, mime_message)
        self.assertEqual(signal_log, [message])
