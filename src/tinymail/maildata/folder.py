from async import assert_main_thread, MailDataOp
from message import Message


class Folder(object):
    def __init__(self, account, imap_name):
        self.account = account
        self.reg = account.reg
        self.remote_do = account.remote_do
        self.imap_name = imap_name
        self.messages = {}
        self.uidvalidity = None
        self._needs_update = True
        self._messages_to_load = set()

    def update_if_needed(self):
        if self._needs_update:
            self._needs_update = False
            self.remote_do(FolderStatusOp(folder=self))

    @assert_main_thread
    def _received_folder_status(self, mbox_status, message_uids):
        if self.uidvalidity is None:
            assert self.messages == {}
            self.uidvalidity = mbox_status['UIDVALIDITY']
        else:
            assert self.uidvalidity == mbox_status['UIDVALIDITY']

        self._messages_to_load.update(message_uids.difference(self.messages))
        self._load_headers_incrementally()

    def _load_headers_incrementally(self):
        if not self._messages_to_load:
            return
        batch = set(sorted(self._messages_to_load)[:10])
        self.remote_do(MessageHeadersOp(folder=self,
                                        message_uids=batch,
                                        uidvalidity=self.uidvalidity))

    @assert_main_thread
    def _received_headers_for_messages(self, message_headers):
        for uid, raw_headers in message_headers.iteritems():
            self._messages_to_load.remove(uid)
            self.messages[uid] = Message(self, uid, self.uidvalidity,
                                         raw_headers)
        self._load_headers_incrementally()
        self.reg.notify((self, 'messages_updated'), folder=self)

class FolderStatusOp(MailDataOp):
    def perform(self, server):
        with server.mailbox(self.folder.imap_name) as mbox:
            return dict(mbox.status), set(mbox.uid_to_num)

    def report(self, status_and_uids):
        self.folder._received_folder_status(*status_and_uids)


class MessageHeadersOp(MailDataOp):
    def perform(self, server):
        with server.mailbox(self.folder.imap_name) as mbox:
            assert mbox.status['UIDVALIDITY'] == self.uidvalidity
            return mbox.message_headers(self.message_uids)

    def report(self, message_headers):
        self.folder._received_headers_for_messages(message_headers)
