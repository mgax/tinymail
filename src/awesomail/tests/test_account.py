from mock import Mock, patch
import unittest
from monocle.callback import defer

class AccountTest(unittest.TestCase):
    def test_list_folders(self):
        from awesomail.account import Account
        account = Account()
        fol1, fol2 = Mock(), Mock()
        account._folders = {'fol1': fol1, 'fol2': fol2}

        folders = list(account.list_folders())

        self.assertEqual(folders, [fol1, fol2])

    def test_get_folder(self):
        from awesomail.account import Account
        account = Account()
        fol1, fol2 = Mock(), Mock()
        account._folders = {'fol1': fol1, 'fol2': fol2}

        ret_fol1 = account.get_folder('fol1')

        self.assertTrue(ret_fol1 is fol1)

class FolderTest(unittest.TestCase):
    def test_list_messages(self):
        from awesomail.account import Folder
        folder = Folder(Mock(), 'fol1')
        msg1, msg2 = Mock(), Mock()
        folder._messages = {1: msg1, 2: msg2}

        messages = list(folder.list_messages())

        self.assertEqual(messages, [msg1, msg2])

class AccountUpdateTest(unittest.TestCase):
    @patch('awesomail.account.get_worker')
    def test_list_folders(self, mock_get_worker):
        from awesomail.account import Account
        folder_names = ['fol1', 'fol2']
        account = Account()
        mock_worker = Mock()
        mock_get_worker.return_value = defer(mock_worker)
        mock_worker.get_mailbox_names.return_value = defer(folder_names)
        mock_worker.get_messages_in_folder.return_value = defer([])

        account.perform_update()

        self.assertEqual(set(f.name for f in account.list_folders()),
                         set(folder_names))

    @patch('awesomail.account.get_worker')
    def test_list_messages(self, mock_get_worker):
        from awesomail.account import Account
        account = Account()
        mock_worker = Mock()
        mock_get_worker.return_value = defer(mock_worker)
        mock_worker.get_mailbox_names.return_value = defer(['fol1'])
        mock_worker.get_messages_in_folder.return_value = defer([6, 8])
        mock_worker.get_message_headers.return_value = defer(Mock())

        account.perform_update()

        fol1 = account.get_folder('fol1')
        self.assertEqual(set(m.msg_id for m in fol1.list_messages()),
                         set([6, 8]))
