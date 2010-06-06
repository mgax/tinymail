import objc
from Foundation import NSObject
import AppKit

from tinymail.maildata.account import Account
from tinymail.maildata.events import Registry

from folder_listing import FolderListingDelegate
from message_listing import MessageListingDelegate
from message_view import MessageViewDelegate
from activity_view import ActivityDelegate

class tinymailAppDelegate(NSObject):
    window = objc.IBOutlet()
    foldersPane = objc.IBOutlet()
    messagesPane = objc.IBOutlet()
    messageView = objc.IBOutlet()
    activityTable = objc.IBOutlet()

    def applicationDidFinishLaunching_(self, notification):
        self.reg = Registry()
        self.the_account = Account(self.reg, read_config())
        self._set_up_ui()
        self.the_account.update_if_needed()

    def _set_up_ui(self):
        FolderListingDelegate.create(self.reg, self.foldersPane,
                                     self.the_account)
        MessageListingDelegate.create(self.reg, self.messagesPane)
        MessageViewDelegate.create(self.reg, self.messageView)
        ActivityDelegate.create(self.reg, self.activityTable)

        self.window.orderWindow_relativeTo_(AppKit.NSWindowAbove,
                self.activityTable.window().windowNumber())

    def applicationWillTerminate_(self, notification):
        self.the_account.cleanup()

def read_config():
    import os
    from os import path
    import json
    cfg_path = path.join(os.environ['HOME'], '.tinymail/account.json')
    with open(cfg_path, 'rb') as f:
        return json.loads(f.read())
