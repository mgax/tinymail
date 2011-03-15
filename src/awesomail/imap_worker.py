import re

list_pattern = re.compile(r'^\((?P<flags>[^\)]*)\) '
                          r'"(?P<delim>[^"]*)" '
                          r'(?P<name>.*)$')
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
        raise NotImplementedError

    def get_message_headers(self, folder_name, msg_id):
        raise NotImplementedError
