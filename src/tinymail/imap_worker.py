import re
import imaplib

list_pattern = re.compile(r'^\((?P<flags>[^\)]*)\) '
                          r'"(?P<delim>[^"]*)" '
                          r'(?P<name>.*)$')

status_pattern = re.compile(r'^(?P<name>[^(]+)\((?P<status>[\w\d\s]*)\)$')

searchuid_pattern = re.compile(r'(?P<index>\d+)\s+\(UID\s*(?P<uid>\d+)'
                               r'\s+FLAGS \((?P<flags>[^\)]*)\)\)$')

class ImapWorkerError(Exception):
    """ Error encountered while talking to IMAP server. """

class ConnectionErrorWrapper(object):
    def __init__(self, conn):
        self.conn = conn

    def __getattr__(self, name):
        method = getattr(self.conn, name)
        def wrapper(*args, **kwargs):
            result = method(*args, **kwargs)
            if name == 'shutdown':
                return
            status, data = result
            if status == 'OK':
                return data
            elif status == 'NO':
                raise ImapWorkerError("Error: %r" % data)
            else:
                raise ImapWorkerError("Unknown status %r" % status)
        return wrapper

class ImapWorker(object):
    def connect(self, host, login_name, login_pass):
        self.conn = ConnectionErrorWrapper(imaplib.IMAP4_SSL(host))
        self.conn.login(login_name, login_pass)

    def disconnect(self):
        import socket
        self.conn.conn.sock.shutdown(socket.SHUT_RDWR)
        self.conn.shutdown()

    def get_mailbox_names(self):
        """ Get a list of all mailbox names in the current account. """

        paths = []
        for entry in self.conn.list():
            m = list_pattern.match(entry)
            assert m is not None
            folder_name = m.group('name').strip('"')
            try:
                folder_name.decode('ascii')
            except UnicodeDecodeError:
                raise ImapWorkerError("Non-ascii mailbox names not supported")
            paths.append(folder_name)

        return paths

    def get_messages_in_folder(self, folder_name):
        """
        Select folder `folder_name`; return folder status + message flags.
        """

        count = self.conn.select(folder_name.encode('ascii'), readonly=True)
        data = self.conn.status(folder_name.encode('ascii'),
                                '(MESSAGES UIDNEXT UIDVALIDITY)')

        m = status_pattern.match(data[0])
        assert m is not None
        assert m.group('name').strip().strip('"') == folder_name.encode('ascii')
        bits = m.group('status').strip().split()
        mbox_status = dict(zip(bits[::2], map(int, bits[1::2])))

        message_data = {}
        if mbox_status['MESSAGES']:
            data = self.conn.fetch('1:*', '(UID FLAGS)')
            for item in data:
                m = searchuid_pattern.match(item)
                assert m is not None
                (uid, index) = (int(m.group('uid')), int(m.group('index')))
                message_data[uid] = {
                    'flags': set(m.group('flags').split()),
                    'index': index,
                }

        return mbox_status, message_data

    def get_message_headers(self, message_indices):
        """ Get headers of specified messagse from current folder. """

        msgs = ','.join(map(str, message_indices))
        data = self.conn.fetch(msgs, '(BODY.PEEK[HEADER] FLAGS)')

        def iter_fragments(data):
            data = iter(data)
            while True:
                fragment = next(data)
                assert len(fragment) == 2, 'unexpected fragment layout'
                yield fragment
                skip = next(data, None)
                assert skip == ')', 'bad closing'

        headers_by_index = {}
        for fragment in iter_fragments(data):
            preamble, mime_headers = fragment
            assert 'BODY[HEADER]' in preamble, 'bad preamble'
            message_index = int(preamble.split(' ', 1)[0])
            headers_by_index[message_index] = mime_headers

        return headers_by_index

    def get_message_body(self, message_index):
        data = self.conn.fetch(str(message_index), '(RFC822)')
        assert len(data) == 2 and data[1] == ')'
        assert isinstance(data[0], tuple) and len(data[0]) == 2
        return data[0][1]
