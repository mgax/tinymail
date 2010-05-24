import traceback

from Foundation import NSObject, objc

from tinymail.maildata.account import Account

from folder_listing import FolderListingDelegate
from message_listing import MessageListingDelegate
from message_view import MessageViewDelegate

class tinymailAppDelegate(NSObject):
    window = objc.IBOutlet()
    foldersPane = objc.IBOutlet()
    messagesPane = objc.IBOutlet()
    messageView = objc.IBOutlet()

    def applicationDidFinishLaunching_(self, notification):
        self.the_account = Account(read_config())
        self._set_up_ui()

    def _set_up_ui(self):
        self.folder_listing = FolderListingDelegate.new()
        self.folder_listing.attach_to_view(self.foldersPane,
                                           self._folder_selected)

        self.message_listing = MessageListingDelegate.new()
        self.message_listing.attach_to_view(self.messagesPane,
                                            self._message_selected)

        self.message_view = MessageViewDelegate.new()
        self.message_view.attach_to_view(self.messageView)

        folder_names = list(self.the_account.folders())
        self.folder_listing.update_folders(folder_names)

    def applicationWillTerminate_(self, notification):
        self.the_account.cleanup()

    def _folder_selected(self, mbox_name):
        update_messages = self.message_listing.update_messages

        if mbox_name is None:
            update_messages([])
            return

        update_messages(list(self.the_account.messages_in_folder(mbox_name)))

    def _message_selected(self, message_handle):
        self.message_view.show_message(message_handle)

def read_config():
    import os
    from os import path
    import json
    cfg_path = path.join(os.environ['HOME'], '.tinymail/account.json')
    with open(cfg_path, 'rb') as f:
        return json.loads(f.read())
