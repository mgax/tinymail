import imaplib
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
        response = self.conn.list()
        assert response[0] == 'OK'

        for entry in response[1]:
            m = list_pattern.match(entry)
            assert m is not None
            folder_path = m.group('name').strip('"')
            yield folder_path

    def cleanup(self):
        self.conn.shutdown()
        print "finished"
