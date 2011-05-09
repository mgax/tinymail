import logging
import re
import imaplib

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)

list_pattern = re.compile(r'^\((?P<flags>[^\)]*)\) '
                          r'"(?P<delim>[^"]*)" '
                          r'(?P<name>.*)$')

status_pattern = re.compile(r'^(?P<name>[^(]+)\((?P<status>[\w\d\s]*)\)$')

uid_pattern = re.compile(r'(?P<index>\d+)\s+\(UID\s*(?P<uid>\d+)\)$')

flags_pattern = re.compile(r'(?P<index>\d+)\s+\(FLAGS\s+'
                           r'\((?P<flags>[^\)]*)\)\)$')

class ImapWorkerError(Exception):
    """ Error encountered while talking to IMAP server. """

class ConnectionErrorWrapper(object):
    def __init__(self, conn):
        self.conn = conn

    def __getattr__(self, name):
        method = getattr(self.conn, name)
        def wrapper(*args, **kwargs):
            result = method(*args, **kwargs)
            status, data = result
            if (status == 'OK') or (status == 'BYE' and name == 'logout'):
                return data
            elif status == 'NO':
                raise ImapWorkerError("Error: %r" % data)
            else:
                raise ImapWorkerError("Unknown status %r" % status)
        return wrapper

# IMAP4_SSL does not call socket.shutdown() before closing socket
if not getattr(imaplib.IMAP4_SSL.shutdown, '_patched_by_tinymail', False):
    def shutdown(self):
        import socket, errno
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except socket.error as e:
            # The server might already have closed the connection
            if e.errno != errno.ENOTCONN:
                raise
        finally:
            self.sock.close()
    shutdown._patched_by_tinymail = True
    imaplib.IMAP4_SSL.shutdown = shutdown
    del shutdown

class ImapWorker(object):
    def connect(self, host, login_name, login_pass):
        log.debug("connecting to %r as %r", host, login_name)
        self.conn = ConnectionErrorWrapper(imaplib.IMAP4_SSL(host))
        self.conn.login(login_name, login_pass)

    def disconnect(self):
        log.debug("disconnecting")
        self.conn.logout()

    def get_mailbox_names(self):
        """ Get a list of all mailbox names in the current account. """

        log.debug("get_mailbox_names")

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

    def select_mailbox(self, name, readonly=True):
        """
        Select a mailbox and check its status. Returns mailbox status
        information.
        """
        name = name.encode('ascii')

        log.debug("select_mailbox %r, readonly=%r", name, readonly)

        self.message_index = {}
        self.message_uid = {}

        count = self.conn.select(name, readonly=readonly)

        data = self.conn.status(name, '(MESSAGES UIDNEXT UIDVALIDITY)')
        m = status_pattern.match(data[0])
        assert m is not None
        assert m.group('name').strip().strip('"') == name
        bits = m.group('status').strip().split()
        mailbox_status = dict(zip(bits[0::2], map(int, bits[1::2])))

        if mailbox_status['MESSAGES']:
            data = self.conn.fetch('1:*', '(UID)')
            for item in data:
                m = uid_pattern.match(item)
                assert m is not None
                (uid, index) = (int(m.group('uid')), int(m.group('index')))
                self.message_index[uid] = index
                self.message_uid[index] = uid

        return mailbox_status

    def get_message_flags(self):
        """ Get flags for all messages in this mailbox. """

        log.debug("get_message_flags")

        data = self.conn.fetch('1:*', '(FLAGS)')

        flags = {}
        for item in data:
            m = flags_pattern.match(item)
            assert m is not None
            uid = self.message_uid[int(m.group('index'))]
            flags[uid] = m.group('flags').split()

        return flags

    def get_message_headers(self, uid_list):
        """ Get headers of specified messagse from current folder. """

        log.debug("get_message_headers for %r", uid_list)

        message_indices = [self.message_index[uid] for uid in uid_list]
        message_indices.sort()
        message_uid = dict((idx, uid) for uid, idx in self.message_index.items())

        msgs = ','.join(map(str, message_indices))
        data = self.conn.fetch(msgs, '(FLAGS BODY.PEEK[HEADER])')

        def iter_fragments(data):
            data = iter(data)
            while True:
                fragment = next(data)
                assert len(fragment) == 2, 'unexpected fragment layout'
                yield fragment
                skip = next(data, None)
                assert skip == ')', 'bad closing'

        headers_by_uid = {}
        for fragment in iter_fragments(data):
            preamble, mime_headers = fragment
            assert 'BODY[HEADER]' in preamble, 'bad preamble'
            idx = int(preamble.split(' ', 1)[0])
            headers_by_uid[message_uid[idx]] = mime_headers

        return headers_by_uid

    def get_message_body(self, uid):
        log.debug("get_message_body for %r", uid)

        data = self.conn.fetch(str(self.message_index[uid]), '(RFC822)')
        assert len(data) == 2 and data[1] == ')'
        assert isinstance(data[0], tuple) and len(data[0]) == 2
        return data[0][1]

    def change_flag(self, uid_list, operation, flag):
        log.debug("change_flag %r %r %r", uid_list, operation, flag)

        OP_MAP = {'add': '+FLAGS',
                  'del': '-FLAGS'}
        message_indices = [self.message_index[uid] for uid in uid_list]
        message_indices.sort()
        msgs = ','.join(map(str, message_indices))
        data = self.conn.store(msgs, OP_MAP[operation], flag)
        # TODO "data" tells us the new flags for all messages

    def close_mailbox(self):
        log.debug("close_mailbox")

        data = self.conn.close()
