from mock import Mock, MagicMock
import unittest2 as unittest
from contextlib import contextmanager
from monocle.callback import defer
from helpers import mock_db, listen_for, mock_worker

def _account_for_test(config=None, db=None):
    from tinymail.account import Account
    if config is None:
        config = {
            'name': 'my test account',
            'host': 'test_host',
            'login_name': 'test_username',
            'login_pass': 'test_password',
        }
    if db is None:
        db = MagicMock()
    return Account(config, db)

class AccountTest(unittest.TestCase):
    def test_list_folders(self):
        account = _account_for_test()
        fol1, fol2 = Mock(), Mock()
        account._folders = {'fol1': fol1, 'fol2': fol2}

        folders = list(account.list_folders())

        self.assertEqual(folders, [fol1, fol2])

    def test_get_folder(self):
        account = _account_for_test()
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

    def test_get_message(self):
        from tinymail.account import Folder
        folder = Folder(Mock(), 'fol1')
        msg1, msg2 = Mock(), Mock()
        folder._messages = {1: msg1, 2: msg2}

        self.assertEqual(folder.get_message(1), msg1)
        self.assertEqual(folder.get_message(2), msg2)

class AccountUpdateTest(unittest.TestCase):

    def test_list_folders(self):
        from tinymail.account import account_updated
        account = _account_for_test()
        folders = {'fol1': {}, 'fol2': {}}

        with mock_worker(**folders):
            with listen_for(account_updated) as caught_signals:
                account.perform_update()

        self.assertEqual(set(f.name for f in account.list_folders()),
                         set(folders))
        self.assertEqual(caught_signals, [(account, {})])

    def test_list_messages(self):
        from tinymail.account import folder_updated
        account = _account_for_test()
        with mock_worker(fol1={6: None}):
            account.perform_update()

        with mock_worker(fol1={6: None, 8: None}):
            with listen_for(folder_updated) as caught_signals:
                account.perform_update()

        fol1 = account.get_folder('fol1')
        self.assertEqual(set(m.uid for m in fol1.list_messages()),
                         set([6, 8]))
        event_data = {'added': [8], 'removed': [], 'flags_changed': []}
        self.assertEqual(caught_signals, [(fol1, event_data)])

    def test_message_removed_on_server(self):
        from tinymail.account import folder_updated
        account = _account_for_test()
        with mock_worker(fol1={6: None, 8: None}):
            account.perform_update()

        with mock_worker(fol1={6: None}):
            with listen_for(folder_updated) as caught_signals:
                account.perform_update()

        fol1 = account.get_folder('fol1')
        self.assertEqual([m.uid for m in fol1.list_messages()], [6])
        event_data = {'added': [], 'removed': [8], 'flags_changed': []}
        self.assertEqual(caught_signals, [(fol1, event_data)])

    def test_only_get_new_headers(self):
        account = _account_for_test()
        with mock_worker(fol1={6: None, 8: None}):
            account.perform_update()

        with mock_worker(fol1={6: None, 8: None, 13: None}) as worker:
            account.perform_update()
            _index = worker.messages_in_folder['fol1'][13]['index']
            worker.get_message_headers.assert_called_once_with(set([_index]))

    def test_empty_folder(self):
        account = _account_for_test()

        with mock_worker(fol1={}) as worker:
            account.perform_update()

        self.assertFalse(worker.get_message_headers.called)

    def test_load_full_message(self):
        from tinymail.account import message_updated
        account = _account_for_test()
        mime_message = "Subject: hi\r\n\r\nHello world!"

        with mock_worker(fol1={6: None}) as worker:
            account.perform_update()
            message = account.get_folder('fol1')._messages[6]
            worker.get_message_body.return_value = defer(mime_message)
            with listen_for(message_updated) as caught_signals:
                message.load_full()

        self.assertEqual(message.raw_full, mime_message)
        self.assertEqual(caught_signals, [(message, {})])

    def test_folder_removed_on_server(self):
        account = _account_for_test()

        with mock_worker(fol1={}, fol2={}):
            account.perform_update()

        with mock_worker(fol1={}):
            account.perform_update()

        self.assertEqual([f.name for f in account.list_folders()], ['fol1'])

    def test_trust_uidvalidity(self):
        account = _account_for_test()
        msg13_data = (13, set([r'\Seen']), "Subject: test message")
        msg13_bis_data = (13, set([r'\Seen']), "Subject: another message")
        with mock_worker(fol1={13: msg13_data}):
            account.perform_update()

        with mock_worker(fol1={13: msg13_bis_data}):
            account.perform_update()

        fol1 = account.get_folder('fol1')
        self.assertEqual([m.raw_headers for m in fol1.list_messages()],
                         [msg13_data[2]])

    def test_uidvalidity_changed(self):
        account = _account_for_test()
        msg13_data = (13, set([r'\Seen']), "Subject: test message")
        msg13_bis_data = (13, set([r'\Seen']), "Subject: another message")
        with mock_worker(fol1={13: msg13_data, 'UIDVALIDITY': 1234}):
            account.perform_update()

        with mock_worker(fol1={13: msg13_bis_data, 'UIDVALIDITY': 1239}):
            account.perform_update()

        fol1 = account.get_folder('fol1')
        self.assertEqual([m.raw_headers for m in fol1.list_messages()],
                         [msg13_bis_data[2]])

    def test_message_flags_changed(self):
        from tinymail.account import folder_updated
        account = _account_for_test()
        msg13_data = (13, set([r'\Seen']), "Subject: test message")
        msg13_bis_data = (13, set([r'\Flagged']), "Subject: test message")
        with mock_worker(fol1={13: msg13_data}):
            account.perform_update()

        with mock_worker(fol1={13: msg13_bis_data}):
            with listen_for(folder_updated) as caught_signals:
                account.perform_update()

        fol1 = account.get_folder('fol1')
        self.assertEqual([m.flags for m in fol1.list_messages()],
                         [set(['\\Flagged'])])
        event_data = {'added': [], 'removed': [], 'flags_changed': [13]}
        self.assertEqual(caught_signals, [(fol1, event_data)])

class PersistenceTest(unittest.TestCase):
    def test_folders(self):
        db = mock_db()
        account = _account_for_test(db=db)

        with mock_worker(myfolder={}) as worker:
            account.perform_update()

        account2 = _account_for_test(db=db)
        folders = list(account2.list_folders())
        self.assertEqual(len(folders), 1)
        self.assertEqual(folders[0].name, 'myfolder')

    def test_folders_removed(self):
        db = mock_db()
        account = _account_for_test(db=db)

        with mock_worker(fol1={}, fol2={}):
            account.perform_update()

        with mock_worker(fol1={}):
            account.perform_update()

        account2 = _account_for_test(db=db)
        self.assertEqual([f.name for f in account2.list_folders()], ['fol1'])

    def test_messages(self):
        db = mock_db()
        account = _account_for_test(db=db)

        msg4_data = (4, set([r'\Seen']), "Subject: test message")
        msg22_data = (22, set([r'\Seen', r'\Answered']), "Subject: blah")

        with mock_worker(myfolder={4: msg4_data, 22: msg22_data}) as worker:
            account.perform_update()

        account2 = _account_for_test(db=db)
        myfolder = account2.get_folder('myfolder')
        messages = list(myfolder.list_messages())
        messages.sort(key=lambda m: m.uid)

        self.assertEqual(len(messages), 2)
        msg4, msg22 = messages
        self.assertEqual(msg4.uid, 4)
        self.assertEqual(msg4.flags, set([r'\Seen']))
        self.assertEqual(msg4.raw_headers, "Subject: test message")
        self.assertEqual(msg22.uid, 22)
        self.assertEqual(msg22.flags, set([r'\Seen', r'\Answered']))
        self.assertEqual(msg22.raw_headers, "Subject: blah")

    def test_message_removed(self):
        db = mock_db()
        account = _account_for_test(db=db)
        with mock_worker(fol1={6: None, 8: None}):
            account.perform_update()

        with mock_worker(fol1={6: None}):
            account.perform_update()

        account2 = _account_for_test(db=db)
        fol1 = account2.get_folder('fol1')
        self.assertEqual([m.uid for m in fol1.list_messages()], [6])

    def test_uidvalidity(self):
        db = mock_db()
        account = _account_for_test(db=db)
        msg13_data = (13, set([r'\Seen']), "Subject: test message")
        with mock_worker(fol1={13: msg13_data, 'UIDVALIDITY': 1234}):
            account.perform_update()

        account2 = _account_for_test(db=db)
        fol1 = account2.get_folder('fol1')
        self.assertEqual(fol1._uidvalidity, 1234)

    def test_uidvalidity_changed(self):
        db = mock_db()
        account = _account_for_test(db=db)
        msg13_data = (13, set([r'\Seen']), "Subject: test message")
        msg13_bis_data = (13, set([r'\Seen']), "Subject: another message")
        with mock_worker(fol1={13: msg13_data, 'UIDVALIDITY': 1234}):
            account.perform_update()
        with mock_worker(fol1={13: msg13_bis_data, 'UIDVALIDITY': 1239}):
            account.perform_update()

        account2 = _account_for_test(db=db)
        fol1 = account2.get_folder('fol1')
        self.assertEqual(fol1._uidvalidity, 1239)
        self.assertEqual([m.raw_headers for m in fol1.list_messages()],
                         [msg13_bis_data[2]])

    def test_message_flags_changed(self):
        db = mock_db()
        account = _account_for_test(db=db)
        msg13_data = (13, set([r'\Seen']), "Subject: test message")
        msg13_bis_data = (13, set([r'\Flagged']), "Subject: test message")
        with mock_worker(fol1={13: msg13_data}):
            account.perform_update()

        with mock_worker(fol1={13: msg13_bis_data}):
            account.perform_update()

        account2 = _account_for_test(db=db)
        fol1 = account2.get_folder('fol1')
        self.assertEqual([m.flags for m in fol1.list_messages()],
                         [set(['\\Flagged'])])

class ModifyFlagsTest(unittest.TestCase):
    def setUp(self):
        self.db = mock_db()
        self.account = _account_for_test(db=self.db)
        self.imap_data = {'fol1': {
            4: (4, set([r'\Seen']), "Subject: test message"),
            15: (15, set([r'\Flagged']), "Subject: whatever"),
            22: (22, set([r'\Seen', r'\Answered']), "Subject: blah"),
        }}
        with mock_worker(**self.imap_data):
            self.account.perform_update()

    def test_add_flag(self):
        from tinymail.account import folder_updated
        fol1 = self.account.get_folder('fol1')

        with mock_worker(**self.imap_data) as worker:
            with listen_for(folder_updated) as caught_signals:
                fol1.change_flag([4, 15], 'add', '\\Seen')

        event_data = {'added': [], 'removed': [], 'flags_changed': [4, 15]}
        self.assertEqual(caught_signals, [(fol1, event_data)])

        idx = lambda uid: worker.messages_in_folder['fol1'][uid]['index']
        worker.change_flag.assert_called_once_with(
                [idx(4), idx(15)], 'add', '\\Seen')

        self.assertEqual(fol1.get_message(4).flags, set(['\\Seen']))
        self.assertEqual(fol1.get_message(15).flags,
                         set(['\\Seen', '\\Flagged']))

        accountB = _account_for_test(db=self.db)
        fol1B = accountB.get_folder('fol1')
        self.assertEqual(fol1B.get_message(4).flags, set(['\\Seen']))
        self.assertEqual(fol1B.get_message(15).flags,
                         set(['\\Seen', '\\Flagged']))

    def test_del_flag(self):
        from tinymail.account import folder_updated
        fol1 = self.account.get_folder('fol1')

        with mock_worker(**self.imap_data) as worker:
            with listen_for(folder_updated) as caught_signals:
                fol1.change_flag([4, 15], 'del', '\\Seen')

        event_data = {'added': [], 'removed': [], 'flags_changed': [4, 15]}
        self.assertEqual(caught_signals, [(fol1, event_data)])

        idx = lambda uid: worker.messages_in_folder['fol1'][uid]['index']
        worker.change_flag.assert_called_once_with(
                [idx(4), idx(15)], 'del', '\\Seen')

        self.assertEqual(fol1.get_message(4).flags, set())
        self.assertEqual(fol1.get_message(15).flags, set(['\\Flagged']))

        accountB = _account_for_test(db=self.db)
        fol1B = accountB.get_folder('fol1')
        self.assertEqual(fol1B.get_message(4).flags, set())
        self.assertEqual(fol1B.get_message(15).flags, set(['\\Flagged']))
