from async import assert_main_thread, MailDataOp
from message import Message


class Folder(object):
    def __init__(self, account, imap_name):
        self.account = account
        self.reg = account.reg
        self.remote_do = account.remote_do
        self.imap_name = imap_name
        self.messages = []
        self._needs_update = True

    def update_if_needed(self):
        if self._needs_update:
            self._needs_update = False
            self.remote_do(MessageHeadersOp(folder=self))

    @assert_main_thread
    def _received_headers_for_messages(self, message_headers):
        messages = []
        for imap_id in sorted(message_headers.iterkeys()):
            messages.append(Message(self, message_headers[imap_id], imap_id))
        self.messages = messages
        self.reg.notify((self, 'messages_updated'), folder=self)

class MessageHeadersOp(MailDataOp):
    def perform(self, server):
        with server.mailbox(self.folder.imap_name) as mbox:
            return mbox.message_headers()

    def report(self, message_headers):
        self.folder._received_headers_for_messages(message_headers)
