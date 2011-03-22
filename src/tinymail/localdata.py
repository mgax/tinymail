from contextlib import contextmanager

class DBFolder(object):
    def __init__(self, account, name):
        self._account = account
        self.name = name

class DBAccount(object):
    def __init__(self, db, name):
        self._db = db
        self.name = name

    def list_folders(self):
        select_query = "select name from folder where account = ?"
        cursor = self._db._connection.execute(select_query, (self.name,))
        for (name,) in cursor:
            yield DBFolder(self, name)

    def add_folder(self, name):
        # TODO make sure we're in a transaction
        # TODO check if the folder already exists
        insert_query = "insert into folder(account, name) values (?, ?)"
        self._db._connection.execute(insert_query, (self.name, name))

class LocalDataDB(object):
    def __init__(self, connection):
        self._connection = connection

    def get_account(self, name):
        return DBAccount(self, name)

    @contextmanager
    def transaction(self):
        yield

def create_db_schema(connection):
    connection.execute("create table folder (account varchar, name varchar)")
