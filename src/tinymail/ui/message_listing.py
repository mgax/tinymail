from Foundation import NSObject

class MessageListingDelegate(NSObject):
    def init(self):
        self.messages = []
        return super(MessageListingDelegate, self).init()

    def attach_to_view(self, table_view, selection_changed):
        col0, col1 = table_view.tableColumns()
        col0.setIdentifier_('From')
        col0.headerCell().setTitle_("Sender")
        col1.setIdentifier_('Subject')
        col1.headerCell().setTitle_("Title")

        table_view.setDelegate_(self)
        table_view.setDataSource_(self)
        self.table_view = table_view
        self.selection_changed = selection_changed

    def update_messages(self, messages):
        self.messages = messages
        self.table_view.reloadData()

    def numberOfRowsInTableView_(self, table_view):
        return len(self.messages)

    def tableView_objectValueForTableColumn_row_(self, table_view, col, row):
        return self.messages[row].mime[col.identifier()]

    def tableView_shouldSelectTableColumn_(self, table_view, col):
        return False

    def tableView_shouldEditTableColumn_row_(self, table_view, col, row):
        return False

    def tableViewSelectionDidChange_(self, notification):
        table_view = notification.object()
        row = table_view.selectedRow()
        new_value = (None if row == -1 else self.messages[row])
        self.selection_changed(new_value)
