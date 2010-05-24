import imaplib
import email
import re

list_pattern = re.compile(r'^\((?P<flags>[^\)]*)\) '
                          r'"(?P<delim>[^"]*)" '
                          r'(?P<name>.*)$')

class ImapServerConnection(object):
    def __init__(self, host, login_name, login_pass):
        self.conn = imaplib.IMAP4_SSL(host)
        #print "connected"
        #print self.conn.capabilities
        self.conn.login(login_name, login_pass)
        #print "logged in"

    def get_mailboxes(self):
        status, entries = self.conn.list()
        assert status == 'OK'

        for entry in entries:
            m = list_pattern.match(entry)
            assert m is not None
            folder_path = m.group('name').strip('"')
            yield folder_path

    def get_messages_in_mailbox(self, mbox_name):
        status, count = self.conn.select(mbox_name, readonly=True)
        assert status == 'OK'

        status, data = self.conn.search(None, 'All')
        assert status == 'OK'
        message_ids = data[0].split()

        # we need to get FLAGS too, otherwise messages are marked as read
        status, data = self.conn.fetch(','.join(message_ids),
                                       '(BODY.PEEK[HEADER] FLAGS)')
        assert status == 'OK'
        data = iter(data)
        while True:
            fragment = next(data)
            assert len(fragment) == 2, 'unexpected fragment layout'
            preamble, headers = fragment
            assert 'BODY[HEADER]' in preamble, 'bad preamble'

            message_id = preamble.split(' ', 1)[0]
            mime_headers = email.message_from_string(headers)

            yield message_id, mime_headers

            closing = next(data, None)
            assert closing == ')', 'bad closing'

    def get_full_message(self, mbox_name, message_id):
        status, count = self.conn.select(mbox_name, readonly=True)
        assert status == 'OK'

        status, data = self.conn.fetch(message_id, '(RFC822)')
        assert status == 'OK'
        assert len(data) == 2 and data[1] == ')'
        assert isinstance(data[0], tuple) and len(data[0]) == 2

        return email.message_from_string(data[0][1])

    def cleanup(self):
        self.conn.shutdown()
        print "finished"
