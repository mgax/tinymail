from Foundation import NSObject

class FolderListingItem(NSObject):
    @classmethod
    def itemWithString_(cls, value):
        item = FolderListingItem.new()
        item.value = value
        return item

class FolderListingDelegate(NSObject):
    def init(self):
        self.items = []
        return super(FolderListingDelegate, self).init()

    def update_folders(self, folder_names):
        for item in self.items:
            item.release()
        self.items = [FolderListingItem.itemWithString_(p).retain()
                      for p in folder_names]
        self.outline_view.reloadData()

    def attach_to_view(self, outline_view, selection_changed):
        outline_view.setDataSource_(self)
        outline_view.setDelegate_(self)
        self.outline_view = outline_view
        self.selection_changed = selection_changed

    def outlineView_numberOfChildrenOfItem_(self, outline_view, item):
        assert item is None
        return len(self.items)

    def outlineView_isItemExpandable_(self, outline_view, item):
        assert isinstance(item, FolderListingItem)
        return False

    def outlineView_child_ofItem_(self, outline_view, child, item):
        assert item is None and -1 < child < len(self.items)
        output = self.items[child]
        return output

    def outlineView_objectValueForTableColumn_byItem_(self, outline_view,
                                                      tableColumn, item):
        assert isinstance(item, FolderListingItem)
        return item.value

    def outlineView_shouldEditTableColumn_item_(self, outline_view,
                                                tableColumn, item):
        return False

    def outlineViewSelectionDidChange_(self, notification):
        outline_view = notification.object()
        row = outline_view.selectedRow()
        new_value = (None if row == -1 else outline_view.itemAtRow_(row).value)
        self.selection_changed(new_value)
