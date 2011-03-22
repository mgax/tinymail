from contextlib import contextmanager

def flatten(flags):
    return ' '.join(sorted(flags))

def unflatten(flat_flags):
    return set(flat_flags.split())

def count_result(result_set):
    return list(result_set)[0][0]

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
        row = (self._account.name, self.name, uid, flatten(flags), headers)
        self._execute(insert_query, row)

    def set_message_flags(self, uid, flags):
        # TODO check arguments
        update_query = ("update message set uid = ? "
                        "where account = ? and folder = ? and uid = ?")
        row = (self._account.name, self.name, uid, flatten(flags))
        self._execute(update_query, row)

    def list_messages(self):
        select_query = ("select uid, flags, headers from message "
                        "where account = ? and folder = ?")
        results = self._execute(select_query, (self._account.name, self.name))
        for uid, flat_flags, headers in results:
            yield uid, unflatten(flat_flags), headers

class DBAccount(object):
    def __init__(self, db, name):
        self._db = db
        self.name = name

    def _execute(self, *args, **kwargs):
        return self._db._execute(*args, **kwargs)

    def list_folders(self):
        select_query = "select name from folder where account = ?"
        cursor = self._execute(select_query, (self.name,))
        for (name,) in cursor:
            yield DBFolder(self, name)

    def add_folder(self, name):
        # TODO check arguments
        select_query = ("select count(*) from folder "
                        "where account = ? and name = ?")
        howmany = count_result(self._execute(select_query, (self.name, name)))
        if howmany > 0:
            raise AssertionError("Account %r already has a folder named %r" %
                                 (self.name, name))
        insert_query = "insert into folder(account, name) values (?, ?)"
        self._execute(insert_query, (self.name, name))

    def get_folder(self, name):
        select_query = ("select count(*) from folder "
                        "where account = ? and name = ?")
        howmany = count_result(self._execute(select_query, (self.name, name)))
        if howmany == 0:
            raise KeyError("Account %r has no folder named %r" %
                           (self.name, name))
        return DBFolder(self, name)

class LocalDataDB(object):
    def __init__(self, connection):
        self._connection = connection
        self._transaction = False

    def _execute(self, *args, **kwargs):
        modif_statements = ['insert', 'update', 'delete', 'replace']
        if args[0].split(' ', 1)[0].lower() in modif_statements:
            assert self._transaction
        return self._connection.execute(*args, **kwargs)

    def get_account(self, name):
        return DBAccount(self, name)

    @contextmanager
    def transaction(self):
        with self._connection:
            self._transaction = True
            try:
                yield
            finally:
                self._transaction = False

def create_db_schema(connection):
    connection.execute("create table folder (account varchar, name varchar)")
    connection.execute("create table message ("
                           "account varchar, folder varchar, "
                           "uid integer, flags varchar, headers text)")
