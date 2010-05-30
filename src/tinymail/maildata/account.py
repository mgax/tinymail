import email

from imapconn import get_imap_loop
from async import spin_off, assert_main_thread, MailDataOp

class Account(object):
    def __init__(self, reg, config):
        self.reg = reg
        self.remote_do, self.remote_cleanup = spin_off(get_imap_loop(config))
        self.gid = 'account'
        self.folders = None

    def update_if_needed(self):
        if self.folders is None:
            self.remote_do(ListFoldersOp(account=self))

    @assert_main_thread
    def _imap_folder_list_loaded(self, imap_folders):
        self.folders = [Folder(self, imap_name) for imap_name in imap_folders]
        self.reg.notify((self, 'folders_updated'), account=self)

    def cleanup(self):
        self.remote_cleanup()

class ListFoldersOp(MailDataOp):
    def perform(self, imap):
        return imap.get_mailboxes()

    def report(self, result):
        self.account._imap_folder_list_loaded(result)


class Folder(object):
    def __init__(self, account, imap_name):
        self.account = account
        self.reg = account.reg
        self.remote_do = account.remote_do
        self.imap_name = imap_name
        self.gid = account.gid + '/' + imap_name
        self.messages = None

    def update_if_needed(self):
        if self.messages is None:
            self.remote_do(MessagesInFolderOp(folder=self))

    @assert_main_thread
    def _imap_message_list_loaded(self, imap_messages):
        messages = []
        for imap_msg_id, mime_headers in imap_messages:
            mime_message = email.message_from_string(mime_headers)
            messages.append(Message(mime_message, imap_msg_id, self))
        self.messages = messages
        self.reg.notify((self, 'messages_updated'), folder=self)

class MessagesInFolderOp(MailDataOp):
    def perform(self, imap):
        return list(imap.get_messages_in_mailbox(self.folder.imap_name))

    def report(self, imap_messages):
        self.folder._imap_message_list_loaded(imap_messages)


class Message(object):
    def __init__(self, headers, imap_id, folder):
        self.folder = folder
        self.remote_do = folder.remote_do
        self.reg = folder.reg
        self.imap_id = imap_id
        self.gid = folder.gid + '/' + imap_id
        self.state = 'headers'
        self.mime = headers

    def update_if_needed(self):
        if self.state != 'full':
            self.remote_do(LoadMessageOp(message=self))

    @assert_main_thread
    def _imap_message_loaded(self, imap_message):
        self.mime = email.message_from_string(imap_message)
        self.state = 'full'
        self.reg.notify((self, 'mime_updated'), message=self)

class LoadMessageOp(MailDataOp):
    def perform(self, imap):
        return imap.get_full_message(self.message.folder.imap_name,
                                     self.message.imap_id)

    def report(self, message_data):
        self.message._imap_message_loaded(message_data)
