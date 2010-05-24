import email
from imapconn import ImapServerConnection

class Account(object):
    def __init__(self, config):
        self.remote = ImapServerConnection(config)

    def folders(self):
        return self.remote.get_mailboxes()

    def messages_in_folder(self, folder_id):
        messages = self.remote.get_messages_in_mailbox(folder_id)
        for imap_id, data in messages:
            headers = email.message_from_string(data)
            yield Message(headers, imap_id, folder_id, self)

    def load_message(self, folder_id, imap_id):
        data = self.remote.get_full_message(folder_id, imap_id)
        return email.message_from_string(data)

    def cleanup(self):
        self.remote.cleanup()

class Message(object):
    def __init__(self, headers, imap_id, folder_id, account):
        self.state = 'headers'
        self.mime = headers
        self.imap_id = imap_id
        self.folder_id = folder_id
        self.account = account

    def ensure_loaded(self):
        if self.state == 'headers':
            self.mime = self.account.load_message(self.folder_id, self.imap_id)
            self.state = 'full'
