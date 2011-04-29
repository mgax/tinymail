from contextlib import contextmanager
import sqlite3

def flatten(flags):
    return ' '.join(sorted(flags))

def unflatten(flat_flags):
    return set(flat_flags.split())

def single_result(result_set):
    return list(result_set)[0][0]

class DBFolder(object):
    def __init__(self, account, name):
        self._account = account
        self.name = name

    def _execute(self, *args, **kwargs):
        return self._account._execute(*args, **kwargs)

    def _executemany(self, *args, **kwargs):
        return self._account._executemany(*args, **kwargs)

    def _count_messages(self, uid):
        select_query = ("select count(*) from message "
                        "where account = ? and folder = ? and uid = ?")
        return single_result(self._execute(select_query,
                            (self._account.name, self.name, uid)))

    def get_uidvalidity(self):
        select_query = ("select uidvalidity from folder "
                        "where account = ? and name = ?")
        return single_result(self._execute(select_query,
                            (self._account.name, self.name)))

    def set_uidvalidity(self, uidvalidity):
        update_query = ("update folder set uidvalidity = ? "
                        "where account = ? and name = ?")
        row = (uidvalidity, self._account.name, self.name)
        self._execute(update_query, row)

    def bulk_add_messages(self, data):
        check_query = ("select count(*) from message where "
                       "account = ? and folder = ? and uid in (%s)"
                       % ','.join(str(row[0]) for row in data))
        res = self._execute(check_query, (self._account.name, self.name))
        assert single_result(res) == 0, "Some messages already exist"

        def sql_rows():
            account_name = self._account.name
            folder_name = self.name
            for uid, flags, headers in data:
                yield (account_name, folder_name,
                       uid, flatten(flags), headers.decode('latin-1'))
        insert_query = ("insert into message"
                        "(account, folder, uid, flags, headers) "
                        "values (?, ?, ?, ?, ?)")
        self._executemany(insert_query, sql_rows())

    def add_message(self, uid, flags, headers):
        return self.bulk_add_messages([(uid, flags, headers)])

    def bulk_del_messages(self, uids):
        sql_uids = ','.join(str(uid) for uid in uids)
        check_query = (
            "select count(uid) from message where "
            "account = ? and folder = ? and uid in (%s)" % sql_uids)
        res = self._execute(check_query, (self._account.name, self.name))
        assert single_result(res) == len(uids), "Message(s) don't exist"

        delete_query = (
            "delete from message where "
            "account = ? and folder = ? and uid in (%s)" % sql_uids)
        self._execute(delete_query, (self._account.name, self.name))

    def del_message(self, uid):
        return self.bulk_del_messages([uid])

    def del_all_messages(self):
        delete_query = "delete from message where account = ? and folder = ?"
        self._execute(delete_query, (self._account.name, self.name))

    def set_message_flags(self, uid, flags):
        # TODO check arguments
        if self._count_messages(uid) == 0:
            msg = ("Folder %r in account %r has no message with uid %r"
                   % (self._account.name, self.name, uid))
            raise KeyError(msg)
        update_query = ("update message set flags = ? "
                        "where account = ? and folder = ? and uid = ?")
        row = (flatten(flags), self._account.name, self.name, uid)
        self._execute(update_query, row)

    def list_messages(self):
        select_query = ("select uid, flags, headers from message "
                        "where account = ? and folder = ?")
        results = self._execute(select_query, (self._account.name, self.name))
        for uid, flat_flags, l1_headers in results:
            yield uid, unflatten(flat_flags), l1_headers.encode('latin-1')

class DBAccount(object):
    def __init__(self, db, name):
        self._db = db
        self.name = name

    def _execute(self, *args, **kwargs):
        return self._db._execute(*args, **kwargs)

    def _executemany(self, *args, **kwargs):
        return self._db._executemany(*args, **kwargs)

    def _count_folders(self, name):
        select_query = ("select count(*) from folder "
                        "where account = ? and name = ?")
        return single_result(self._execute(select_query, (self.name, name)))

    def list_folders(self):
        select_query = "select name from folder where account = ?"
        cursor = self._execute(select_query, (self.name,))
        for (name,) in cursor:
            yield DBFolder(self, name)

    def add_folder(self, name):
        # TODO check arguments
        if self._count_folders(name) > 0:
            raise AssertionError("Account %r already has a folder named %r" %
                                 (self.name, name))
        insert_query = "insert into folder(account, name) values (?, ?)"
        self._execute(insert_query, (self.name, name))
        return DBFolder(self, name)

    def get_folder(self, name):
        if self._count_folders(name) == 0:
            raise KeyError("Account %r has no folder named %r" %
                           (self.name, name))
        return DBFolder(self, name)

    def del_folder(self, name):
        if self._count_folders(name) == 0:
            raise KeyError("Account %r has no folder named %r" %
                           (self.name, name))
        delete_query = "delete from folder where account = ? and name = ?"
        self._execute(delete_query, (self.name, name))

class LocalDataDB(object):
    def __init__(self, connection):
        self._connection = connection
        self._transaction = False

    def _execute(self, *args, **kwargs):
        modif_statements = ['insert', 'update', 'delete', 'replace']
        if args[0].split(' ', 1)[0].lower() in modif_statements:
            assert self._transaction
        return self._connection.execute(*args, **kwargs)

    def _executemany(self, *args, **kwargs):
        assert self._transaction
        return self._connection.executemany(*args, **kwargs)

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

    def close(self):
        self._connection.close()

def create_db_schema(connection):
    connection.execute("create table if not exists "
                       "folder (account varchar, name varchar, "
                               "uidvalidity integer)")
    connection.execute("create table if not exists "
                       "message (account varchar, folder varchar, "
                                "uid integer, flags varchar, headers text)")

def open_local_db(db_path):
    connection = sqlite3.connect(db_path)
    create_db_schema(connection)
    return LocalDataDB(connection)
