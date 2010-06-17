import email


class Message(object):
    def __init__(self, folder, uid, raw_headers, flags):
        self.folder = folder
        self.remote_do = folder.remote_do
        self.reg = folder.reg
        self.uid = uid
        self.headers = email.message_from_string(raw_headers)
        self.flags = flags

    def fullmsg_ready(self, raw_message):
        mime = email.message_from_string(raw_message)
        self.reg.notify((self, 'full_message'), message=self, mime=mime)

    def request_fullmsg(self):
        self.folder.request_fullmsg(self)
