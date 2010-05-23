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

    def _folder_selected(self, name):
        messages = ([] if name is None else [{'sender': name,
                                              'subject': 'asdf'}])
        self.message_listing.update_messages(messages)

def connect_to_imap_server():
    import os
    from os import path
    import json
    cfg_path = path.join(os.environ['HOME'], '.tinymail/account.json')
    with open(cfg_path, 'rb') as f:
        cfg_data = json.loads(f.read()).items()
    return ImapServerConnection(**dict( (str(k),v) for (k,v) in cfg_data ))
