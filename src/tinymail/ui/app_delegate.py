import traceback

from Foundation import NSObject, objc

from tinymail.maildata.imapconn import ImapServerConnection
from folder_listing import set_up_folder_listing
from message_listing import MessageListingDataSource

class tinymailAppDelegate(NSObject):
    window = objc.IBOutlet()
    foldersPane = objc.IBOutlet()
    messagesPane = objc.IBOutlet()

    def applicationDidFinishLaunching_(self, notification):
        self.imap_server = connect_to_imap_server()
        set_up_folder_listing(self.imap_server, self.foldersPane,
                              self._folder_selected)
        self.message_listing = MessageListingDataSource.new()
        self.message_listing.attach_to_view(self.messagesPane)

    def applicationWillTerminate_(self, notification):
        self.imap_server.cleanup()

    def _folder_selected(self, mbox_name):
        update_messages = self.message_listing.update_messages

        if mbox_name is None:
            update_messages([])
            return

        messages = []
        for message in self.imap_server.get_messages_in_mailbox(mbox_name):
            messages.append({
                'subject': message['Subject'],
                'sender': message['From'],
            })
        update_messages(messages)

def connect_to_imap_server():
    import os
    from os import path
    import json
    cfg_path = path.join(os.environ['HOME'], '.tinymail/account.json')
    with open(cfg_path, 'rb') as f:
        cfg_data = json.loads(f.read()).items()
    return ImapServerConnection(**dict( (str(k),v) for (k,v) in cfg_data ))
