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
