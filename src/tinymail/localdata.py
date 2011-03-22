from contextlib import contextmanager

class DBFolder(object):
    def __init__(self, account, name):
        self._account = account
        self.name = name

class DBAccount(object):
    def __init__(self, db, name):
        self._db = db
        self.name = name

    def _execute(self, *args, **kwargs):
        return self._db._connection.execute(*args, **kwargs)

    def list_folders(self):
        select_query = "select name from folder where account = ?"
        cursor = self._execute(select_query, (self.name,))
        for (name,) in cursor:
            yield DBFolder(self, name)

    def add_folder(self, name):
        # TODO make sure we're in a transaction
        # TODO check if the folder already exists
        insert_query = "insert into folder(account, name) values (?, ?)"
        self._execute(insert_query, (self.name, name))

    def get_folder(self, name):
        select_query = ("select count(*) from folder "
                        "where account = ? and name = ?")
        howmany = list(self._execute(select_query, (self.name, name)))[0][0]
        if howmany == 0:
            raise KeyError("Account %r has no folder named %r" %
                           (self.name, name))
        return DBFolder(self, name)

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
