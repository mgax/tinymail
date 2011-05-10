import logging
from monocle import _o, Return
from blinker import Signal
from async import AsyncJob, start_worker, SimpleWorkerManager
from imap_worker import ImapWorker

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

account_opened = Signal()
account_updated = Signal()
folder_updated = Signal()
message_updated = Signal()

class Account(object):
    def __init__(self, config, db):
        self.name = config['name']
        self.config = config
        self._db = db
        self._folders = {}
        self._load_from_db()
        self._sync_job = None
        self.worker_manager = SimpleWorkerManager(self._create_worker,
                                                  self._desotry_worker)

    def get_imap_config(self):
        return dict( (k, self.config[k]) for k in
                     ('host', 'login_name', 'login_pass') )

    def list_folders(self):
        return self._folders.itervalues()

    def get_folder(self, name):
        return self._folders[name]

    def _load_from_db(self):
        # TODO move this into an async job?
        db_account = self._db.get_account(self.name)
        db_account_folders = list(db_account.list_folders())
        for db_folder in db_account_folders:
            name = db_folder.name
            folder = Folder(self, name)
            folder._uidvalidity = db_folder.get_uidvalidity()
            self._folders[name] = folder
            for uid, flags, raw_headers in db_folder.list_messages():
                message = Message(folder, uid, flags, raw_headers)
                folder._messages[uid] = message
        account_opened.send(self)

    def perform_update(self):
        if self._sync_job is not None:
            return
        cb = AccountUpdateJob(self).start()
        if not hasattr(cb, 'result'):
            self._sync_job = cb

    @_o
    def _create_worker(self):
        worker = _new_imap_worker()
        yield worker.connect(**self.get_imap_config())
        yield Return(worker)

    @_o
    def _desotry_worker(self, worker):
        yield worker.disconnect()
        worker.done()

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

    def change_flag(self, uid_list, operation, flag):
        FolderChangeFlagJob(self, uid_list, operation, flag).start()

    def copy_messages(self, uid_list, dst_folder):
        if dst_folder.account is not self.account:
            raise NotImplementedError("Copying messages accross accounts "
                                      "is not implemented yet.")

        FolderCopyMessagesJob(self, uid_list, dst_folder).start()

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

        yield Return(self.raw_full)

def _new_imap_worker():
    return start_worker(ImapWorker())

class AccountUpdateJob(AsyncJob):
    def __init__(self, account):
        self.account = account

    @_o
    def do_stuff(self):
        wm = self.account.worker_manager
        worker = yield wm.get_worker()

        try:
            yield self.update_account(worker)

        finally:
            self.account._sync_job = None
            yield wm.hand_back_worker(worker)

    @_o
    def update_account(self, worker):
        log.debug("Begin update of account %r", self.account.name)

        mailbox_names = yield worker.get_mailbox_names()

        new_mailbox_names = set(mailbox_names) - set(self.account._folders)
        removed_mailbox_names = set(self.account._folders) - set(mailbox_names)

        if new_mailbox_names:
            db = self.account._db
            db_account = db.get_account(self.account.name)
            with db.transaction():
                for name in new_mailbox_names:
                    log.info("New folder %r", name)
                    db_account.add_folder(name)
                    self.account._folders[name] = Folder(self.account, name)

        if removed_mailbox_names:
            db = self.account._db
            db_account = db.get_account(self.account.name)
            with db.transaction():
                for name in removed_mailbox_names:
                    log.info("Folder %r was removed", name)
                    db_account.del_folder(name)
                    del self.account._folders[name]

        account_updated.send(self.account)

        for name in mailbox_names:
            yield self.update_folder(worker, self.account._folders[name])

        log.info("Update finished for account %r", self.account.name)

    @_o
    def update_folder(self, worker, folder):
        log.debug("Updating folder %r", folder.name)
        db = self.account._db
        db_folder = db.get_account(self.account.name).get_folder(folder.name)
        mbox_status = yield worker.select_mailbox(folder.name)
        message_flags = yield worker.get_message_flags()
        assert mbox_status['MESSAGES'] == len(message_flags)

        if mbox_status['UIDVALIDITY'] != folder._uidvalidity:
            if folder._uidvalidity is not None:
                log.info("Folder %r UIDVALIDITY has changed", folder.name)
                folder._messages.clear()
            folder._uidvalidity = mbox_status['UIDVALIDITY']
            with db.transaction():
                db_folder.del_all_messages()
                db_folder.set_uidvalidity(folder._uidvalidity)

        server_message_ids = set(message_flags)
        our_message_ids = set(folder._messages)
        new_message_ids = server_message_ids - our_message_ids
        removed_message_ids = our_message_ids - server_message_ids

        event_data = {'added': [], 'removed': [], 'flags_changed': []}

        # messages added on server; add them locally too
        if new_message_ids:
            headers_by_uid = yield worker.get_message_headers(new_message_ids)
            with db.transaction():
                sql_msgs = []
                for uid, raw_headers in headers_by_uid.iteritems():
                    flags = set(message_flags[uid])
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
                new_flags = set(message_flags[uid])
                if message.flags != new_flags:
                    message.flags = new_flags
                    db_folder.set_message_flags(uid, new_flags)
                    flags_changed += 1
                    event_data['flags_changed'].append(uid)

        if new_message_ids or removed_message_ids or flags_changed:
            folder_updated.send(folder, **event_data)

        log.info("Finished updating folder %r: %d messages "
                 "(%d new, %d del, %d flags)",
                 folder.name, mbox_status['MESSAGES'],
                 len(new_message_ids), len(removed_message_ids), flags_changed)

        yield worker.close_mailbox()


class MessageLoadFullJob(AsyncJob):
    def __init__(self, message):
        self.message = message

    @_o
    def do_stuff(self):
        wm = self.message.folder.account.worker_manager
        worker = yield wm.get_worker()

        try:
            yield self.load_full_message(worker)

        finally:
            yield wm.hand_back_worker(worker)

    @_o
    def load_full_message(self, worker):
        message = self.message
        log.debug("Loading full message %r in folder %r",
                 message.uid, message.folder.name)

        yield worker.select_mailbox(message.folder.name)
        body = yield worker.get_message_body(message.uid)
        message.raw_full = body

        message_updated.send(message)

        self.message._load_job = None

        yield worker.close_mailbox()


class FolderChangeFlagJob(AsyncJob):
    def __init__(self, folder, uid_list, operation, flag):
        self.folder = folder
        self.uid_list = uid_list
        self.operation = operation
        self.flag = flag

    @_o
    def do_stuff(self):
        wm = self.folder.account.worker_manager
        worker = yield wm.get_worker()

        try:
            yield self.change_messages_flag(worker)

        finally:
            yield wm.hand_back_worker(worker)

    @_o
    def change_messages_flag(self, worker):
        log.debug("Changing flags in folder %r, messages %r: %r %r",
                  self.folder, self.uid_list, self.operation, self.flag)

        yield worker.select_mailbox(self.folder.name, readonly=False)
        yield worker.change_flag(self.uid_list, self.operation, self.flag)

        db = self.folder.account._db
        with db.transaction():
            db_account = db.get_account(self.folder.account.name)
            db_folder = db_account.get_folder(self.folder.name)
            for uid in self.uid_list:
                message = self.folder._messages[uid]
                if self.operation == 'add':
                    message.flags.add(self.flag)
                elif self.operation == 'del':
                    message.flags.discard(self.flag)
                else:
                    raise ValueError('Unknown operation %r' % self.operation)
                db_folder.set_message_flags(uid, message.flags)

        event_data = {
            'added': [],
            'removed': [],
            'flags_changed': self.uid_list,
        }
        folder_updated.send(self.folder, **event_data)

        yield worker.close_mailbox()


class FolderCopyMessagesJob(AsyncJob):
    def __init__(self, src_folder, src_uids, dst_folder):
        self.src_folder = src_folder
        self.src_uids = src_uids
        self.dst_folder = dst_folder

    @_o
    def do_stuff(self):
        wm = self.src_folder.account.worker_manager
        worker = yield wm.get_worker()

        try:
            yield self.copy_messages(worker)

        finally:
            yield wm.hand_back_worker(worker)

    @_o
    def copy_messages(self, worker):
        log.debug("Copying messages %r from %r to %r",
                  self.src_uids, self.src_folder, self.dst_folder)

        yield worker.select_mailbox(self.src_folder.name)
        result = yield worker.copy_messages(self.src_uids,
                                              self.dst_folder.name)
        assert set(result['uid_map']) == set(self.src_uids)
        # TODO check UIDVALIDITY

        db = self.dst_folder.account._db
        with db.transaction():
            db_account = db.get_account(self.dst_folder.account.name)
            dst_db_folder = db_account.get_folder(self.dst_folder.name)

            sql_msgs = []
            for src_uid, dst_uid in result['uid_map'].iteritems():
                src_message = self.src_folder.get_message(src_uid)
                flags = set(src_message.flags)
                raw_headers = src_message.raw_headers

                sql_msgs.append((dst_uid, flags, raw_headers))
                dst_message = Message(self.dst_folder, dst_uid,
                                      flags, raw_headers)
                self.dst_folder._messages[dst_uid] = dst_message
            dst_db_folder.bulk_add_messages(sql_msgs)

        event_data = {
            'added': sorted(result['uid_map'].values()),
            'removed': [],
            'flags_changed': [],
        }
        folder_updated.send(self.dst_folder, **event_data)

        yield worker.close_mailbox()
