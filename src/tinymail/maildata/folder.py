from async import assert_main_thread, MailDataOp
from message import Message


class Folder(object):
    def __init__(self, account, imap_name):
        self.account = account
        self.reg = account.reg
        self.remote_do = account.remote_do
        self.imap_name = imap_name
        self.messages = None

    def update_if_needed(self):
        if self.messages is None:
            self.remote_do(MessagesInFolderOp(folder=self))

    @assert_main_thread
    def _imap_message_list_loaded(self, imap_messages):
        messages = []
        for imap_msg_id, mime_headers in imap_messages:
            messages.append(Message(mime_headers, imap_msg_id, self))
        self.messages = messages
        self.reg.notify((self, 'messages_updated'), folder=self)

class MessagesInFolderOp(MailDataOp):
    def perform(self, imap):
        return list(imap.get_messages_in_mailbox(self.folder.imap_name))

    def report(self, imap_messages):
        self.folder._imap_message_list_loaded(imap_messages)
