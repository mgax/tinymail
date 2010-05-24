import traceback

from Foundation import NSObject, objc

from tinymail.maildata.imapconn import ImapServerConnection
from folder_listing import set_up_folder_listing
from message_listing import MessageListingDataSource
from message_view import MessageView

class tinymailAppDelegate(NSObject):
    window = objc.IBOutlet()
    foldersPane = objc.IBOutlet()
    messagesPane = objc.IBOutlet()
    messageView = objc.IBOutlet()

    def applicationDidFinishLaunching_(self, notification):
        self.imap_server = connect_to_imap_server()

        set_up_folder_listing(self.imap_server, self.foldersPane,
                              self._folder_selected)

        self.message_listing = MessageListingDataSource.new()
        self.message_listing.attach_to_view(self.messagesPane,
                                            self._message_selected)

        self.message_view = MessageView.new()
        self.message_view.attach_to_view(self.messageView)

    def applicationWillTerminate_(self, notification):
        self.imap_server.cleanup()

    def _folder_selected(self, mbox_name):
        update_messages = self.message_listing.update_messages

        if mbox_name is None:
            update_messages([])
            return

        messages = []
        imap_messages = self.imap_server.get_messages_in_mailbox(mbox_name)
        for (imap_id, mime_headers) in imap_messages:
            messages.append({
                'subject': mime_headers['Subject'],
                'sender': mime_headers['From'],
                'imap_id': imap_id,
                'mbox_name': mbox_name,
            })
        update_messages(messages)

    def _message_selected(self, message):
        show_message = self.message_view.show_message

        if message is None:
            show_message(None)
            return

        mime_message = self.imap_server.get_full_message(
                                message['mbox_name'], message['imap_id'])
        show_message(mime_message)

def connect_to_imap_server():
    import os
    from os import path
    import json
    cfg_path = path.join(os.environ['HOME'], '.tinymail/account.json')
    with open(cfg_path, 'rb') as f:
        cfg_data = json.loads(f.read()).items()
    return ImapServerConnection(**dict( (str(k),v) for (k,v) in cfg_data ))
