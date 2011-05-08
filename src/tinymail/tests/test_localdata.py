import unittest2 as unittest
from helpers import mock_db

msg1 = (13, set([r'\Seen']), "Subject: hi!")
msg2 = (15, set(), "Subject: message 2")
msg3 = (19, set(), "Subject: another")

def db_account_folder(db, account_name, folder_name):
    with db.transaction():
        return db.get_account(account_name).add_folder(folder_name)

class LocalDataTest(unittest.TestCase):
    def test_folder(self):
        db = mock_db()
        db_account = db.get_account('my account')

        with db.transaction():
            db_account.add_folder('mailing-lists')

        folder = db_account.get_folder('mailing-lists')
        self.assertEqual(folder.name, 'mailing-lists')

        self.assertRaises(KeyError, db_account.get_folder, 'no-such-folder')

    def test_add_existing_folder(self):
        db = mock_db()
        db_account = db.get_account('my account')

        with db.transaction():
            db_account.add_folder('INBOX')

        with db.transaction():
            self.assertRaises(AssertionError, db_account.add_folder, 'INBOX')

    def test_remove_folder(self):
        db = mock_db()
        db_account = db.get_account('my account')

        with db.transaction():
            db_account.add_folder('INBOX')

        with db.transaction():
            db_account.del_folder('INBOX')

        self.assertEqual(list(db_account.list_folders()), [])

    def test_remove_nonexistent_folder(self):
        db = mock_db()
        db_account = db.get_account('my account')

        with db.transaction():
            self.assertRaises(KeyError,
                              db_account.del_folder, 'no-such-folder')

    def test_list_folders(self):
        db = mock_db()
        db_account = db.get_account('my account')
        self.assertEqual(list(db_account.list_folders()), [])

        with db.transaction():
            db_account.add_folder('INBOX')
            db_account.add_folder('archive')

        names = set(f.name for f in db_account.list_folders())
        self.assertEqual(len(names), 2)
        self.assertEqual(names, set(['INBOX', 'archive']))

    def test_folder_uidvalidity(self):
        db = mock_db()
        db_account = db.get_account('my account')
        with db.transaction():
            db_account.add_folder('archive')
        db_folder = db_account.get_folder('archive')
        self.assertIs(db_folder.get_uidvalidity(), None)

        with db.transaction():
            db_folder.set_uidvalidity(1234)

        self.assertEqual(db_folder.get_uidvalidity(), 1234)

    def test_messages(self):
        db = mock_db()
        db_folder = db_account_folder(db, 'my account', 'archive')

        with db.transaction():
            db_folder.add_message(*msg1)
            db_folder.add_message(*msg2)

        messages = sorted(db_folder.list_messages())
        self.assertEqual(messages, [msg1, msg2])

    def test_message_nonascii_headers(self):
        db = mock_db()
        db_folder = db_account_folder(db, 'my account', 'archive')

        unicode_msg = (24, set([r'\Seen']), "Subject: hi!\xec\xec\xff")

        with db.transaction():
            db_folder.add_message(*unicode_msg)

        messages = sorted(db_folder.list_messages())
        self.assertEqual(messages, [unicode_msg])
        self.assertTrue(type(messages[0][2]) is str)

    def test_add_existing_message(self):
        db = mock_db()
        db_folder = db_account_folder(db, 'my account', 'archive')
        with db.transaction():
            db_folder.add_message(*msg1)

        with db.transaction():
            self.assertRaises(AssertionError, db_folder.add_message, *msg1)

    def test_bulk_add_messages(self):
        db = mock_db()
        db_folder = db_account_folder(db, 'my account', 'archive')

        with db.transaction():
            db_folder.bulk_add_messages([msg1, msg2])

        messages = sorted(db_folder.list_messages())
        self.assertEqual(messages, [msg1, msg2])

    def test_bulk_add_messages_exising(self):
        db = mock_db()
        db_folder = db_account_folder(db, 'my account', 'archive')
        with db.transaction():
            db_folder.add_message(*msg1)

        with db.transaction():
            self.assertRaises(AssertionError,
                              db_folder.bulk_add_messages, [msg1, msg2])

    def test_remove_message(self):
        db = mock_db()
        db_folder = db_account_folder(db, 'my account', 'archive')
        with db.transaction():
            db_folder.add_message(*msg1)
            db_folder.add_message(*msg2)

        with db.transaction():
            db_folder.del_message(13)

        self.assertEqual(list(db_folder.list_messages()), [msg2])

    def test_remove_nonexistent_message(self):
        db = mock_db()
        db_folder = db_account_folder(db, 'my account', 'archive')

        with db.transaction():
            self.assertRaises(AssertionError, db_folder.del_message, 13)

    def test_bulk_remove_messages(self):
        db = mock_db()
        db_folder = db_account_folder(db, 'my account', 'archive')
        with db.transaction():
            db_folder.bulk_add_messages([msg1, msg2, msg3])

        with db.transaction():
            db_folder.bulk_del_messages([msg1[0], msg3[0]])

        self.assertEqual(list(db_folder.list_messages()), [msg2])

    def test_bulk_remove_messages_nonexistent(self):
        db = mock_db()
        db_folder = db_account_folder(db, 'my account', 'archive')
        with db.transaction():
            db_folder.bulk_add_messages([msg1])

        with db.transaction():
            self.assertRaises(AssertionError,
                              db_folder.bulk_del_messages, [msg1[0], msg3[0]])

    def test_remove_all_messagse(self):
        db = mock_db()
        db_folder = db_account_folder(db, 'my account', 'archive')
        with db.transaction():
            db_folder.add_message(*msg1)
            db_folder.add_message(*msg2)

        with db.transaction():
            db_folder.del_all_messages()

        self.assertEqual(list(db_folder.list_messages()), [])

    def test_set_message_flags(self):
        db = mock_db()
        db_folder = db_account_folder(db, 'my account', 'archive')

        with db.transaction():
            db_folder.add_message(*msg1)
            db_folder.add_message(*msg2)

        with db.transaction():
            db_folder.set_message_flags(13, set([r'\Seen', r'\Answered']))

        msg1bis = (13, set([r'\Seen', r'\Answered']), "Subject: hi!")

        messages = sorted(db_folder.list_messages())
        self.assertEqual(messages, [msg1bis, msg2])

    def test_set_message_flags_no_message(self):
        db = mock_db()
        db_folder = db_account_folder(db, 'my account', 'archive')

        with db.transaction():
            self.assertRaises(KeyError, db_folder.set_message_flags,
                              13, set([r'\Seen', r'\Answered']))

    def test_require_transactions(self):
        db = mock_db()
        db_account = db.get_account('my account')
        db_folder = db_account_folder(db, 'my account', 'archive')
        with db.transaction():
            db_folder.add_message(13, set([r'\Seen']), "Subject: hi!")

        self.assertRaises(AssertionError, db_account.add_folder, 'other')
        self.assertRaises(AssertionError, db_folder.add_message,
                          17, set([r'\Seen']), "Subject: smth")
        self.assertRaises(AssertionError, db_folder.set_message_flags,
                          13, set([r'\Seen', r'\Answered']))

    def test_separate_accounts(self):
        msg1 = (13, set([r'\Seen']), "Subject: hi!")
        msg2 = (22, set([r'\Flagged']), "Subject: bye!")
        db = mock_db()
        A_fol = db_account_folder(db, 'A', 'fol')
        B_fol = db_account_folder(db, 'B', 'fol')
        with db.transaction():
            A_fol.add_message(*msg1)
            B_fol.add_message(*msg2)

        def _msgs(db, account_name, folder_name):
            account = db.get_account(account_name)
            folder = account.get_folder(folder_name)
            return list(folder.list_messages())
        self.assertEqual(_msgs(db, 'A', 'fol'), [msg1])
        self.assertEqual(_msgs(db, 'B', 'fol'), [msg2])

# TODO test with non-ascii headers. just in case.
