from contextlib import contextmanager

class DBFolder(object):
    def __init__(self, account, name):
        self._account = account
        self.name = name

    def _execute(self, *args, **kwargs):
        return self._account._execute(*args, **kwargs)

    def add_message(self, uid, flags, headers):
        # TODO check arguments
        insert_query = ("insert into message"
                        "(account, folder, uid, flags, headers) "
                        "values (?, ?, ?, ?, ?)")
        flat_flags = ' '.join(sorted(flags))
        row = (self._account.name, self.name, uid, flat_flags, headers)
        self._execute(insert_query, row)

    def list_messages(self):
        select_query = ("select uid, flags, headers from message "
                        "where account = ? and folder = ?")
        results = self._execute(select_query, (self._account.name, self.name))
        for uid, flat_flags, headers in results:
            flags = set(flat_flags.split())
            yield uid, flags, headers

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
        # TODO check arguments
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
    connection.execute("create table message ("
                           "account varchar, folder varchar, "
                           "uid integer, flags varchar, headers text)")
