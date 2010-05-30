from Foundation import NSObject, NSURL, NSString, NSISOLatin1StringEncoding

class MessageViewDelegate(NSObject):
    @classmethod
    def create(cls, reg, web_view):
        self = cls.new()
        self.reg = reg
        self.web_view = web_view
        self._message = None
        self.reg.subscribe('ui.message_selected', self.handle_message_selected)
        return self

    def handle_message_selected(self, message):
        if self._message is not None:
            self.reg.unsubscribe((self._message, 'mime_updated'),
                                 self.handle_mime_updated)

        self._message = message
        if self._message is None:
            self._update_view_with_string("")
            return

        self._update_view_with_string(self._message.mime.as_string())
        self.reg.subscribe((self._message, 'mime_updated'),
                           self.handle_mime_updated)
        self._message.update_if_needed()

    def handle_mime_updated(self, message):
        assert message is self._message, '%r is not %r' % (message.imap_id, self._message.imap_id)
        self._update_view_with_string(self._message.mime.as_string())

    def _update_view_with_string(self, str_data):
        ns_str = NSString.stringWithString_(str_data.decode('latin-1'))
        data = ns_str.dataUsingEncoding_(NSISOLatin1StringEncoding)
        url = NSURL.URLWithString_('about:blank')
        self.web_view.mainFrame().loadData_MIMEType_textEncodingName_baseURL_(
                    data, 'text/plain', 'latin-1', url)
