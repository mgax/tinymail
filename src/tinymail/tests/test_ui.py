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
