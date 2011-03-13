from mock import Mock
import unittest

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
        folder = Folder()
        msg1, msg2 = Mock(), Mock()
        folder._messages = {1: msg1, 2: msg2}

        messages = list(folder.list_messages())

        self.assertEqual(messages, [msg1, msg2])
