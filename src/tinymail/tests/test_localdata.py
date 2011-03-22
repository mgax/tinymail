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
        self.assertEqual(list(db_account.list_folders()), [])

        with db.transaction():
            db_account.add_folder('INBOX')

        folders = list(db_account.list_folders())
        self.assertEqual(len(folders), 1)
        self.assertEqual(folders[0].name, 'INBOX')
