from Foundation import NSObject

class MessageListingDelegate(NSObject):
    @classmethod
    def create(cls, reg, table_view):
        self = cls.new()
        self.reg = reg
        self.table_view = table_view
        table_view.setDelegate_(self)
        table_view.setDataSource_(self)
        self._set_up_columns()
        self.reg.subscribe('ui.folder_selected', self.handle_folder_selected)
        return self

    def _set_up_columns(self):
        col0, col1 = self.table_view.tableColumns()
        col0.setIdentifier_('From')
        col0.headerCell().setTitle_("Sender")
        col1.setIdentifier_('Subject')
        col1.headerCell().setTitle_("Title")

    def init(self):
        self.messages = []
        self._folder = None
        return super(MessageListingDelegate, self).init()

    def handle_folder_selected(self, folder):
        if self._folder is not None:
            self.reg.unsubscribe((self._folder, 'messages_updated'),
                                 self.handle_messages_updated)

        self._folder = folder
        if self._folder is None:
            self.messages_updated({})
            return

        self.messages_updated(self._folder.messages)
        self.reg.subscribe((self._folder, 'messages_updated'),
                           self.handle_messages_updated)
        self._folder.update_if_needed()

    def handle_messages_updated(self, folder):
        assert folder is self._folder
        self.messages_updated(folder.messages)

    def messages_updated(self, messages):
        self.messages = [msg for (uid, msg) in sorted(messages.iteritems())]
        self.table_view.reloadData()

    def numberOfRowsInTableView_(self, table_view):
        return len(self.messages)

    def tableView_objectValueForTableColumn_row_(self, table_view, col, row):
        return self.messages[row].headers[col.identifier()]

    def tableView_shouldSelectTableColumn_(self, table_view, col):
        return False

    def tableView_shouldEditTableColumn_row_(self, table_view, col, row):
        return False

    def tableViewSelectionDidChange_(self, notification):
        table_view = notification.object()
        row = table_view.selectedRow()
        new_value = (None if row == -1 else self.messages[row])

        self.reg.notify('ui.message_selected', message=new_value)
