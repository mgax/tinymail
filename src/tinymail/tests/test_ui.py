import unittest2 as unittest
from monocle import _o
from blinker import signal
from helpers import mock_db, listen_for, mock_worker

def get_app_delegate():
    import AppKit
    app = AppKit.NSApplication.sharedApplication()
    return app.delegate()

def _account_for_test(config=None):
    from tinymail.account import Account
    if config is None:
        config = {
            'host': 'test_host',
            'login_name': 'test_username',
            'login_pass': 'test_password',
        }
    return Account(config, mock_db())

def sleep(delay):
    from PyObjCTools import AppHelper
    from monocle.core import Callback
    cb = Callback()
    AppHelper.callLater(delay, cb, None)
    return cb

def cleanup_ui(app_delegate):
    from tinymail.ui_delegates import FolderListing, MessageListing
    from tinymail.account import Folder
    MessageListing.create(app_delegate.messagesPane, Folder(None, 'f'))
    FolderListing.create(app_delegate.foldersPane, _account_for_test())

def objc_index_set(values):
    from Foundation import NSMutableIndexSet
    mutable_index_set = NSMutableIndexSet.new()
    for value in values:
        mutable_index_set.addIndex_(value)
    return mutable_index_set

def account_with_folders(**folders):
    account = _account_for_test()
    with mock_worker(**folders):
        account.perform_update()
    return account

class FolderListingTest(unittest.TestCase):
    def tearDown(self):
        cleanup_ui(get_app_delegate())

    def test_show_folders(self):
        from tinymail.ui_delegates import FolderListing
        account = _account_for_test()
        folders_pane = get_app_delegate().foldersPane
        folder_listing = FolderListing.create(folders_pane, account)

        with mock_worker(fol1={6: None, 8: None}, fol2={}):
            account.perform_update()

        cell1 = folders_pane.preparedCellAtColumn_row_(0, 0)
        self.assertEqual(cell1.objectValue(), 'fol1')
        cell2 = folders_pane.preparedCellAtColumn_row_(0, 1)
        self.assertEqual(cell2.objectValue(), 'fol2')

    def test_select_folder(self):
        from tinymail.ui_delegates import FolderListing
        account = _account_for_test()
        folders_pane = get_app_delegate().foldersPane
        folder_listing = FolderListing.create(folders_pane, account)

        with mock_worker(fol1={6: None, 8: None}, fol2={}):
            account.perform_update()

        with listen_for(signal('ui-folder-selected')) as caught_signals:
            rows = objc_index_set([1])
            folders_pane.selectRowIndexes_byExtendingSelection_(rows, False)

        self.assertEqual(caught_signals, [
            (folder_listing, {'folder': account.get_folder('fol2')}),
        ])

class MessageListingTest(unittest.TestCase):
    def tearDown(self):
        cleanup_ui(get_app_delegate())

    def test_show_messages(self):
        from tinymail.ui_delegates import MessageListing
        msg6 = (6, [r'\Seen'], "From: me\nSubject: test message")
        msg8 = (8, [r'\Seen'], "From: her\nSubject: another test message")
        account = account_with_folders(fol1={6: msg6, 8: msg8})
        folder = account.get_folder('fol1')
        messages_pane = get_app_delegate().messagesPane

        message_listing = MessageListing.create(messages_pane, folder)

        sender1 = messages_pane.preparedCellAtColumn_row_(0, 0)
        subject1 = messages_pane.preparedCellAtColumn_row_(1, 0)
        self.assertEqual(sender1.objectValue(), "me")
        self.assertEqual(subject1.objectValue(), "test message")

        sender2 = messages_pane.preparedCellAtColumn_row_(0, 1)
        subject2 = messages_pane.preparedCellAtColumn_row_(1, 1)
        self.assertEqual(sender2.objectValue(), "her")
        self.assertEqual(subject2.objectValue(), "another test message")

    def test_select_message(self):
        from tinymail.ui_delegates import MessageListing
        msg6 = (6, [r'\Seen'], "From: me\nSubject: test message")
        msg8 = (8, [r'\Seen'], "From: her\nSubject: another test message")
        account = account_with_folders(fol1={6: msg6, 8: msg8})
        fol1 = account.get_folder('fol1')
        messages_pane = get_app_delegate().messagesPane

        message_listing = MessageListing.create(messages_pane, fol1)

        with listen_for(signal('ui-message-selected')) as caught_signals:
            rows = objc_index_set([1])
            messages_pane.selectRowIndexes_byExtendingSelection_(rows, False)

        self.assertEqual(caught_signals, [
            (message_listing, {'message': fol1.get_message(8)}),
        ])
