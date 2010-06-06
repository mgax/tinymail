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
            self.remote_do(MessagesInFolderOp(folder=self))

    @assert_main_thread
    def _received_headers_for_messages(self, imap_messages):
        self.messages[:] = [Message(self, mime_headers, imap_msg_id)
                            for imap_msg_id, mime_headers in imap_messages]
        self.reg.notify((self, 'messages_updated'), folder=self)

class MessagesInFolderOp(MailDataOp):
    def perform(self, server):
        return list(server.get_messages_in_mailbox(self.folder.imap_name))

    def report(self, imap_messages):
        self.folder._received_headers_for_messages(imap_messages)
