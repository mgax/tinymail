import email

from imapconn import ImapServerConnection

class Account(object):
    def __init__(self, config):
        self.remote = ImapServerConnection(config)
        self.folders = None

    def call_with_folders(self, callback):
        if self.folders is None:
            self.folders = [Folder(imap_name, self)
                            for imap_name in self.remote.get_mailboxes()]
        callback(self.folders)

    def cleanup(self):
        self.remote.cleanup()


class Folder(object):
    def __init__(self, imap_name, account):
        self.imap_name = imap_name
        self.account = account
        self.messages = None

    def call_with_messages(self, callback):
        if self.messages is None:
            messages = []
            imap = self.account.remote
            imap_messages = imap.get_messages_in_mailbox(self.imap_name)
            for imap_msg_id, mime_headers in imap_messages:
                mime_message = email.message_from_string(mime_headers)
                messages.append(Message(mime_message, imap_msg_id, self))
            self.messages = messages

        callback(self.messages)


class Message(object):
    def __init__(self, headers, imap_id, folder):
        self.state = 'headers'
        self.mime = headers
        self.imap_id = imap_id
        self.folder = folder

    def call_when_loaded(self, callback):
        if self.state != 'full':
            imap = self.folder.account.remote
            imap_message = imap.get_full_message(self.folder.imap_name,
                                                 self.imap_id)
            self.mime = email.message_from_string(imap_message)
            self.state = 'full'

        callback(self)
