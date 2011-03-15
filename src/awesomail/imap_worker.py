import re

list_pattern = re.compile(r'^\((?P<flags>[^\)]*)\) '
                          r'"(?P<delim>[^"]*)" '
                          r'(?P<name>.*)$')

status_pattern = re.compile(r'^(?P<name>[^(]+)\((?P<status>[\w\d\s]*)\)$')

searchuid_pattern = re.compile(r'(?P<index>\d+)\s+\(UID\s*(?P<uid>\d+)'
                               r'\s+FLAGS \((?P<flags>[^\)]*)\)\)$')

class ImapWorker(object):
    def get_mailbox_names(self):
        status, entries = self.conn.list()
        assert status == 'OK'

        paths = []
        for entry in entries:
            m = list_pattern.match(entry)
            assert m is not None
            folder_path = m.group('name').strip('"')
            paths.append(folder_path)

        return paths

    def get_messages_in_folder(self, folder_name):
        status, count = self.conn.select(folder_name, readonly=True)
        assert status == 'OK'

        status, data = self.conn.status(folder_name,
                                        '(MESSAGES UIDNEXT UIDVALIDITY)')
        assert status == 'OK'

        m = status_pattern.match(data[0])
        assert m is not None
        assert m.group('name').strip().strip('"') == folder_name
        bits = m.group('status').strip().split()
        mbox_status = dict(zip(bits[::2], map(int, bits[1::2])))

        message_data = {}
        if mbox_status['MESSAGES']:
            status, data = self.conn.fetch('1:*', '(UID FLAGS)')
            assert status == 'OK'

            for item in data:
                m = searchuid_pattern.match(item)
                assert m is not None
                (uid, index) = (int(m.group('uid')), int(m.group('index')))
                message_data[uid] = {
                    'flags': set(m.group('flags').split()),
                    'index': index,
                }

        return mbox_status, message_data

    def get_message_headers(self, folder_name, msg_id):
        raise NotImplementedError
