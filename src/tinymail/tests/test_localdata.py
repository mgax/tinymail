import unittest2 as unittest

def make_test_db():
    import sqlite3
    from tinymail.localdata import LocalDataDB, create_db_schema
    connection = sqlite3.connect(':memory:')
    create_db_schema(connection)
    return LocalDataDB(connection)

class LocalDataTest(unittest.TestCase):
    def test_folder(self):
        db = make_test_db()
        db_account = db.get_account('some account name')

        with db.transaction():
            db_account.add_folder('mailing-lists')

        folder = db_account.get_folder('mailing-lists')
        self.assertEqual(folder.name, 'mailing-lists')

        self.assertRaises(KeyError, db_account.get_folder, 'no-such-folder')

    def test_list_folders(self):
        db = make_test_db()
        db_account = db.get_account('some account name')
        self.assertEqual(list(db_account.list_folders()), [])

        with db.transaction():
            db_account.add_folder('INBOX')
            db_account.add_folder('archive')

        names = set(f.name for f in db_account.list_folders())
        self.assertEqual(len(names), 2)
        self.assertEqual(names, set(['INBOX', 'archive']))

    def test_messages(self):
        db = make_test_db()
        with db.transaction():
            db_account = db.get_account('some account name')
            db_account.add_folder('archive')
            db_folder = db_account.get_folder('archive')

        msg1 = (13, set([r'\Seen']), "Subject: hi!")
        msg2 = (15, set(), "Subject: message 2")

        with db.transaction():
            db_folder.add_message(*msg1)
            db_folder.add_message(*msg2)

        messages = sorted(db_folder.list_messages())
        self.assertEqual(messages, [msg1, msg2])

    def test_set_message_flags(self):
        db = make_test_db()
        with db.transaction():
            db_account = db.get_account('some account name')
            db_account.add_folder('archive')
            db_folder = db_account.get_folder('archive')

        msg1 = (13, set([r'\Seen']), "Subject: hi!")
        msg2 = (15, set(), "Subject: message 2")

        with db.transaction():
            db_folder.add_message(*msg1)
            db_folder.add_message(*msg2)

        with db.transaction():
            db_folder.set_message_flags(13, set([r'\Seen', r'\Answered']))

        msg1bis = (13, set([r'\Seen', r'\Answered']), "Subject: hi!")

        messages = sorted(db_folder.list_messages())
        self.assertEqual(messages, [msg1, msg2])

    def test_require_transactions(self):
        db = make_test_db()
        with db.transaction():
            db_account = db.get_account('some account name')
            db_account.add_folder('archive')
            db_folder = db_account.get_folder('archive')
            db_folder.set_message_flags(13, set([r'\Seen']))

        self.assertRaises(AssertionError, db_account.add_folder, 'other')
        self.assertRaises(AssertionError, db_folder.add_message,
                          17, set([r'\Seen']), "Subject: smth")
        self.assertRaises(AssertionError, db_folder.set_message_flags,
                          13, set([r'\Seen', r'\Answered']))

# TODO test with non-ascii headers. just in case.
