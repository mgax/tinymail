import unittest2 as unittest
from monocle import _o
from blinker import signal
from helpers import mock_db, listen_for, mock_worker, AsyncTestCase

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
    from tinymail.ui_delegates import AccountController, FolderController
    from tinymail.account import Folder

    fc = FolderController.controllerWithFolder_(Folder(None, 'f'))
    app_delegate.setFolderController_(fc)

    ac = AccountController.newWithAccount_(_account_for_test())
    app_delegate.setAccountController_(ac)

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

class AccountControllerTest(AsyncTestCase):
    def tearDown(self):
        cleanup_ui(get_app_delegate())

    def test_show_folders(self):
        from tinymail.ui_delegates import AccountController
        account = _account_for_test()
        folders_pane = get_app_delegate().foldersPane
        with mock_worker(fol1={6: None, 8: None}, fol2={}):
            account.perform_update()

        account_controller = AccountController.newWithAccount_(account)
        get_app_delegate().setAccountController_(account_controller)

        cell1 = folders_pane.preparedCellAtColumn_row_(0, 0)
        self.assertEqual(cell1.objectValue(), 'fol1')
        cell2 = folders_pane.preparedCellAtColumn_row_(0, 1)
        self.assertEqual(cell2.objectValue(), 'fol2')

    def test_folders_updated(self):
        from tinymail.ui_delegates import AccountController
        account = _account_for_test()
        folders_pane = get_app_delegate().foldersPane
        account_controller = AccountController.newWithAccount_(account)
        get_app_delegate().setAccountController_(account_controller)

        with mock_worker(fol2={}, fol3={}):
            account.perform_update()

        cell1 = folders_pane.preparedCellAtColumn_row_(0, 0)
        self.assertEqual(cell1.objectValue(), 'fol2')
        cell2 = folders_pane.preparedCellAtColumn_row_(0, 1)
        self.assertEqual(cell2.objectValue(), 'fol3')

    def test_select_folder(self):
        from tinymail.ui_delegates import AccountController
        account = _account_for_test()
        folders_pane = get_app_delegate().foldersPane
        with mock_worker(fol1={6: None, 8: None}, fol2={}):
            account.perform_update()
        account_controller = AccountController.newWithAccount_(account)
        get_app_delegate().setAccountController_(account_controller)

        with listen_for(signal('ui-folder-selected')) as caught_signals:
            rows = objc_index_set([1])
            folders_pane.selectRowIndexes_byExtendingSelection_(rows, False)

        self.assertEqual(caught_signals, [
            (account_controller, {'folder': account.get_folder('fol2')}),
        ])

class MessageListingTest(AsyncTestCase):
    def tearDown(self):
        cleanup_ui(get_app_delegate())

    def test_show_messages(self):
        from tinymail.ui_delegates import FolderController
        msg6 = (6, [r'\Seen'], "From: me\nSubject: test message")
        msg8 = (8, [r'\Seen'], "From: her\nSubject: another test message")
        account = account_with_folders(fol1={6: msg6, 8: msg8})
        folder = account.get_folder('fol1')
        app_delegate = get_app_delegate()
        messages_pane = app_delegate.messagesPane
        folder_controller = FolderController.controllerWithFolder_(folder)
        app_delegate.setFolderController_(folder_controller)


        sender1 = messages_pane.preparedCellAtColumn_row_(0, 0)
        subject1 = messages_pane.preparedCellAtColumn_row_(1, 0)
        self.assertEqual(sender1.objectValue(), "me")
        self.assertEqual(subject1.objectValue(), "test message")

        sender2 = messages_pane.preparedCellAtColumn_row_(0, 1)
        subject2 = messages_pane.preparedCellAtColumn_row_(1, 1)
        self.assertEqual(sender2.objectValue(), "her")
        self.assertEqual(subject2.objectValue(), "another test message")

    def test_update_messages(self):
        from tinymail.ui_delegates import FolderController
        msg6 = (6, [r'\Seen'], "From: me\nSubject: test message")
        msg8 = (8, [r'\Seen'], "From: her\nSubject: another test message")
        account = account_with_folders(fol1={})
        folder = account.get_folder('fol1')
        app_delegate = get_app_delegate()
        messages_pane = app_delegate.messagesPane
        folder_controller = FolderController.controllerWithFolder_(folder)
        app_delegate.setFolderController_(folder_controller)

        with mock_worker(fol1={6: msg6, 8: msg8}):
            account.perform_update()

        subject1 = messages_pane.preparedCellAtColumn_row_(1, 0)
        self.assertEqual(subject1.objectValue(), "test message")

        subject2 = messages_pane.preparedCellAtColumn_row_(1, 1)
        self.assertEqual(subject2.objectValue(), "another test message")

    def test_select_message(self):
        from tinymail.ui_delegates import FolderController
        msg6 = (6, [r'\Seen'], "From: me\nSubject: test message")
        msg8 = (8, [r'\Seen'], "From: her\nSubject: another test message")
        account = account_with_folders(fol1={6: msg6, 8: msg8})
        fol1 = account.get_folder('fol1')
        app_delegate = get_app_delegate()
        messages_pane = app_delegate.messagesPane
        folder_controller = FolderController.controllerWithFolder_(fol1)
        app_delegate.setFolderController_(folder_controller)

        with listen_for(signal('ui-message-selected')) as caught_signals:
            rows = objc_index_set([1])
            messages_pane.selectRowIndexes_byExtendingSelection_(rows, False)

        self.assertEqual(caught_signals, [
            (folder_controller, {'message': fol1.get_message(8)}),
        ])
