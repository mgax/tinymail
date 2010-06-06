import email
from async import assert_main_thread, MailDataOp


class Message(object):
    def __init__(self, folder, imap_uid, uidvalidity, raw_headers):
        assert isinstance(imap_uid, int)
        self.folder = folder
        self.remote_do = folder.remote_do
        self.reg = folder.reg
        self.imap_uid = imap_uid
        self.uidvalidity = uidvalidity
        self.state = 'headers'
        self.mime = email.message_from_string(raw_headers)

    def update_if_needed(self):
        if self.state != 'full':
            self.remote_do(LoadMessageOp(message=self))

    @assert_main_thread
    def _received_full_message(self, raw_message):
        self.mime = email.message_from_string(raw_message)
        self.state = 'full'
        self.reg.notify((self, 'mime_updated'), message=self)

class LoadMessageOp(MailDataOp):
    def perform(self, server):
        with server.mailbox(self.message.folder.imap_name) as mbox:
            assert mbox.status['UIDVALIDITY'] == self.message.uidvalidity
            return mbox.full_message(self.message.imap_uid)

    def report(self, raw_message):
        self.message._received_full_message(raw_message)
