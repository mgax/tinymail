import logging
from monocle import _o
from blinker import signal
from async import AsyncJob, start_worker
from imap_worker import ImapWorker

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

_signals = [signal(name) for name in
            ('account-updated', 'folder-updated', 'message-updated')]

class Account(object):
    def __init__(self, config, db):
        self.name = "The Account"
        self.config = config
        self._db = db
        self._folders = {}
        self._load_from_db()

    def get_imap_config(self):
        return dict( (k, self.config[k]) for k in
                     ('host', 'login_name', 'login_pass') )

    def list_folders(self):
        return self._folders.itervalues()

    def get_folder(self, name):
        return self._folders[name]

    def _load_from_db(self):
        # TODO move this into an async job?
        db_account = self._db.get_account('the-account')
        db_account_folders = list(db_account.list_folders())
        for db_folder in db_account_folders:
            name = db_folder.name
            folder = Folder(self, name)
            folder._uidvalidity = db_folder.get_uidvalidity()
            self._folders[name] = folder
            for uid, flags, raw_headers in db_folder.list_messages():
                message = Message(folder, uid, flags, raw_headers)
                folder._messages[uid] = message

    def perform_update(self):
        job = AccountUpdateJob(self)
        job.start()
        assert job.failure is None

class Folder(object):
    def __init__(self, account, name):
        self.account = account
        self.name = name
        self._messages = {}
        self._uidvalidity = None

    def list_messages(self):
        return self._messages.itervalues()

class Message(object):
    def __init__(self, folder, uid, flags, raw_headers):
        self.folder = folder
        self.uid = uid
        self.flags = flags
        self.raw_headers = raw_headers
        self.raw_full = None

    def load_full(self):
        job = MessageLoadFullJob(self)
        job.start()
        assert job.failure is None

def get_worker():
    return start_worker(ImapWorker())

class AccountUpdateJob(AsyncJob):
    def __init__(self, account):
        self.account = account

    @_o
    def do_stuff(self):
        log.debug("Begin update of account %r", self.account.name)
        worker = get_worker()
        yield worker.connect(**self.account.get_imap_config())
        mailbox_names = yield worker.get_mailbox_names()

        new_mailbox_names = set(mailbox_names) - set(self.account._folders)
        removed_mailbox_names = set(self.account._folders) - set(mailbox_names)

        if new_mailbox_names:
            db = self.account._db
            db_account = db.get_account('the-account')
            with db.transaction():
                for name in new_mailbox_names:
                    log.info("New folder %r", name)
                    db_account.add_folder(name)
                    self.account._folders[name] = Folder(self.account, name)

        if removed_mailbox_names:
            db = self.account._db
            db_account = db.get_account('the-account')
            with db.transaction():
                for name in removed_mailbox_names:
                    log.info("Folder %r was removed", name)
                    db_account.del_folder(name)
                    del self.account._folders[name]

        signal('account-updated').send(self.account)

        for name in mailbox_names:
            yield self.update_folder(worker, self.account._folders[name])

        yield worker.disconnect()
        log.info("Update finished for account %r", self.account.name)

    @_o
    def update_folder(self, worker, folder):
        log.debug("Updating folder %r", folder.name)
        mbox_status, message_data = yield worker.get_messages_in_folder(folder.name)

        if mbox_status['UIDVALIDITY'] != folder._uidvalidity:
            if folder._uidvalidity is not None:
                log.info("Folder %r UIDVALIDITY has changed", folder.name)
                folder._messages.clear()
            folder._uidvalidity = mbox_status['UIDVALIDITY']
            db = self.account._db
            db_account = db.get_account('the-account')
            db_folder = db_account.get_folder(folder.name)
            with db.transaction():
                db_folder.del_all_messages()
                db_folder.set_uidvalidity(folder._uidvalidity)

        new_message_ids = set(message_data) - set(folder._messages)
        removed_message_ids = set(folder._messages) - set(message_data)

        new_indices = set()
        index_to_uuid = {}
        for uid in new_message_ids:
            index = message_data[uid]['index']
            new_indices.add(index)
            index_to_uuid[index] = uid

        if new_indices:
            db = self.account._db
            db_account = db.get_account('the-account')
            db_folder = db_account.get_folder(folder.name)
            with db.transaction():
                headers_by_index = yield worker.get_message_headers(new_indices)
                for index, raw_headers in headers_by_index.iteritems():
                    uid = index_to_uuid[index]
                    flags = message_data[uid]['flags']
                    db_folder.add_message(uid, flags, raw_headers)
                    message = Message(folder, uid, flags, raw_headers)
                    folder._messages[uid] = message

            signal('folder-updated').send(folder)

        if removed_message_ids:
            db = self.account._db
            db_account = db.get_account('the-account')
            db_folder = db_account.get_folder(folder.name)
            with db.transaction():
                for uid in removed_message_ids:
                    del folder._messages[uid]
                    db_folder.del_message(uid)

        log.info("Finished updating folder %r: %d messages (%d new, %d del)",
                 folder.name, len(message_data),
                 len(new_indices), len(removed_message_ids))

class MessageLoadFullJob(AsyncJob):
    def __init__(self, message):
        self.message = message

    @_o
    def do_stuff(self):
        message = self.message
        log.debug("Loading full message %r in folder %r",
                 message.uid, message.folder.name)
        worker = get_worker()
        config = dict( (k, message.folder.account.config[k]) for k in
                       ('host', 'login_name', 'login_pass') )
        yield worker.connect(**config)

        mbox_status, message_data = yield worker.get_messages_in_folder(message.folder.name)
        uuid_to_index = {}
        for uid, msg_info in message_data.iteritems():
            index = msg_info['index']
            uuid_to_index[uid] = index

        body = yield worker.get_message_body(uuid_to_index[message.uid])
        message.raw_full = body

        signal('message-updated').send(message)
