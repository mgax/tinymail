import email
from async import assert_main_thread, MailDataOp


class Message(object):
    def __init__(self, folder, raw_headers, imap_id):
        assert isinstance(imap_id, int)
        self.folder = folder
        self.remote_do = folder.remote_do
        self.reg = folder.reg
        self.imap_id = imap_id
        self.state = 'headers'
        self.mime = email.message_from_string(raw_headers)

    def update_if_needed(self):
        if self.state != 'full':
            self.remote_do(LoadMessageOp(message=self))

    @assert_main_thread
    def _received_full_message(self, imap_message):
        self.mime = email.message_from_string(imap_message)
        self.state = 'full'
        self.reg.notify((self, 'mime_updated'), message=self)

class LoadMessageOp(MailDataOp):
    def perform(self, server):
        return server.get_full_message(self.message.folder.imap_name,
                                     self.message.imap_id)

    def report(self, message_data):
        self.message._received_full_message(message_data)
