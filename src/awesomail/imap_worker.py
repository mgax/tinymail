class ImapWorker(object):
    def get_mailbox_names(self):
        raise NotImplementedError

    def get_messages_in_folder(self, folder_name):
        raise NotImplementedError

    def get_message_headers(self, folder_name, msg_id):
        raise NotImplementedError
