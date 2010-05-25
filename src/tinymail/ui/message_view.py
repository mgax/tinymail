from Foundation import NSObject, NSURL, NSString, NSISOLatin1StringEncoding

class MessageViewDelegate(NSObject):
    def attach_to_view(self, web_view):
        self.web_view = web_view

    def show_message(self, message):
        if message is None:
            self._update_view_with_string("")
        else:
            message.call_when_loaded(self._display_message)

    def _display_message(self, message):
        self._update_view_with_string(message.mime.as_string())

    def _update_view_with_string(self, str_data):
        ns_str = NSString.stringWithString_(str_data.decode('latin-1'))
        data = ns_str.dataUsingEncoding_(NSISOLatin1StringEncoding)
        url = NSURL.URLWithString_('about:blank')
        self.web_view.mainFrame().loadData_MIMEType_textEncodingName_baseURL_(
                    data, 'text/plain', 'latin-1', url)
