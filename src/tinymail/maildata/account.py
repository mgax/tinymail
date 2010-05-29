import email

from imapconn import get_imap_loop
from async import spin_off, assert_main_thread, MailDataOp

class Account(object):
    def __init__(self, config):
        self.remote_do, self.remote_cleanup = spin_off(get_imap_loop(config))
        self.folders = None

    def call_with_folders(self, callback):
        @assert_main_thread
        def done():
            callback(self.folders)

        if self.folders is not None:
            done()
        else:
            self.remote_do(ListFoldersOp(account=self, callback=done))

    @assert_main_thread
    def _imap_folder_list_loaded(self, imap_folders):
        self.folders = [Folder(imap_name, self) for imap_name in imap_folders]

    def cleanup(self):
        self.remote_cleanup()

class ListFoldersOp(MailDataOp):
    def perform(self, imap):
        return imap.get_mailboxes()

    def report(self, result):
        self.account._imap_folder_list_loaded(result)
        self.callback()


class Folder(object):
    def __init__(self, imap_name, account):
        self.imap_name = imap_name
        self.account = account
        self.remote_do = account.remote_do
        self.messages = None

    def call_with_messages(self, callback):
        @assert_main_thread
        def done():
            callback(self.messages)

        if self.messages is not None:
            done()
        else:
            self.remote_do(MessagesInFolderOp(folder=self, callback=done))

    @assert_main_thread
    def _imap_message_list_loaded(self, imap_messages):
        messages = []
        for imap_msg_id, mime_headers in imap_messages:
            mime_message = email.message_from_string(mime_headers)
            messages.append(Message(mime_message, imap_msg_id, self))
        self.messages = messages

class MessagesInFolderOp(MailDataOp):
    def perform(self, imap):
        return list(imap.get_messages_in_mailbox(self.folder.imap_name))

    def report(self, imap_messages):
        self.folder._imap_message_list_loaded(imap_messages)
        self.callback()


class Message(object):
    def __init__(self, headers, imap_id, folder):
        self.state = 'headers'
        self.mime = headers
        self.imap_id = imap_id
        self.folder = folder
        self.remote_do = folder.remote_do

    def call_when_loaded(self, callback):
        @assert_main_thread
        def done():
            callback(self)

        if self.state == 'full':
            done()
        else:
            self.remote_do(LoadMessageOp(message=self, callback=done))

    @assert_main_thread
    def _imap_message_loaded(self, imap_message):
        self.mime = email.message_from_string(imap_message)
        self.state = 'full'

class LoadMessageOp(MailDataOp):
    def perform(self, imap):
        return imap.get_full_message(self.message.folder.imap_name,
                                     self.message.imap_id)

    def report(self, message_data):
        self.message._imap_message_loaded(message_data)
        self.callback()
