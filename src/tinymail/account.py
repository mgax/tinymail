import logging
from monocle import _o, Return
from blinker import signal
from async import AsyncJob, start_worker
from imap_worker import ImapWorker

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

_signals = [signal(name) for name in
            ('account-opened', 'account-updated', 'folder-updated',
             'message-updated')]

class Account(object):
    def __init__(self, config, db):
        self.name = "The Account"
        self.config = config
        self._db = db
        self._folders = {}
        self._load_from_db()
        self._sync_job = None

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
        signal('account-opened').send(self)

    def perform_update(self):
        if self._sync_job is not None:
            return
        cb = AccountUpdateJob(self).start()
        if not hasattr(cb, 'result'):
            self._sync_job = cb

class Folder(object):
    def __init__(self, account, name):
        self.account = account
        self.name = name
        self._messages = {}
        self._uidvalidity = None

    def list_messages(self):
        return self._messages.itervalues()

    def get_message(self, uid):
        return self._messages[uid]

class Message(object):
    def __init__(self, folder, uid, flags, raw_headers):
        self.folder = folder
        self.uid = uid
        self.flags = flags
        self.raw_headers = raw_headers
        self.raw_full = None
        self._load_job = None

    @_o
    def load_full(self):
        if self._load_job is not None:
            yield self._load_job

        elif self.raw_full is None:
            cb = MessageLoadFullJob(self).start()
            if not hasattr(cb, 'result'):
                self._load_job = cb
            yield cb

        yield Return(self)

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

        self.account._sync_job = None

    @_o
    def update_folder(self, worker, folder):
        log.debug("Updating folder %r", folder.name)
        db = self.account._db
        db_folder = db.get_account('the-account').get_folder(folder.name)
        mbox_status, message_data = yield worker.get_messages_in_folder(folder.name)

        if mbox_status['UIDVALIDITY'] != folder._uidvalidity:
            if folder._uidvalidity is not None:
                log.info("Folder %r UIDVALIDITY has changed", folder.name)
                folder._messages.clear()
            folder._uidvalidity = mbox_status['UIDVALIDITY']
            with db.transaction():
                db_folder.del_all_messages()
                db_folder.set_uidvalidity(folder._uidvalidity)

        server_message_ids = set(message_data)
        our_message_ids = set(folder._messages)
        new_message_ids = server_message_ids - our_message_ids
        removed_message_ids = our_message_ids - server_message_ids

        event_data = {'added': [], 'removed': [], 'flags_changed': []}

        # messages added on server; add them locally too
        new_indices = set()
        index_to_uuid = {}
        for uid in new_message_ids:
            index = message_data[uid]['index']
            new_indices.add(index)
            index_to_uuid[index] = uid

        if new_indices:
            with db.transaction():
                headers_by_index = yield worker.get_message_headers(new_indices)
                sql_msgs = []
                for index, raw_headers in headers_by_index.iteritems():
                    uid = index_to_uuid[index]
                    flags = message_data[uid]['flags']
                    sql_msgs.append((uid, flags, raw_headers))
                    message = Message(folder, uid, flags, raw_headers)
                    folder._messages[uid] = message
                    event_data['added'].append(uid)
                db_folder.bulk_add_messages(sql_msgs)

        # messages removed on server; remove them locally too
        if removed_message_ids:
            with db.transaction():
                for uid in removed_message_ids:
                    del folder._messages[uid]
                    event_data['removed'].append(uid)
                db_folder.bulk_del_messages(removed_message_ids)

        # for existing messages, update their flags
        flags_changed = 0
        with db.transaction():
            for uid in our_message_ids & server_message_ids:
                message = folder._messages[uid]
                new_flags = message_data[uid]['flags']
                if message.flags != new_flags:
                    message.flags = new_flags
                    db_folder.set_message_flags(uid, new_flags)
                    flags_changed += 1
                    event_data['flags_changed'].append(uid)

        if new_indices or removed_message_ids or flags_changed:
            signal('folder-updated').send(folder, **event_data)

        log.info("Finished updating folder %r: %d messages "
                 "(%d new, %d del, %d flags)",
                 folder.name, len(message_data),
                 len(new_indices), len(removed_message_ids), flags_changed)

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

        self.message._load_job = None
