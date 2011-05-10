import unittest2 as unittest


class ImapIndexTranscodingTest(unittest.TestCase):

    def test_invalid_strings(self):
        from tinymail.imap_worker import array_from_imap_str

        data = ['', 'asdf', '1:', ':1', '1,2:', '1:,2', '1:3:5', '1a', 'a1']

        for str_value in data:
            self.assertRaises(ValueError, array_from_imap_str, str_value)

    def test_invalid_sequences(self):
        from tinymail.imap_worker import imap_str_from_sequence

        data = [[3, 2], [1,2,3,4,3], [1,2,3,3,4]]

        for seq in data:
            print seq
            self.assertRaises(ValueError, imap_str_from_sequence, seq)
            print 'ok'

    def test_conversion(self):
        from tinymail.imap_worker import array_from_imap_str
        from tinymail.imap_worker import imap_str_from_sequence

        data = {
            '1': [1],
            '1,3,5': [1, 3, 5],
            '1:5': [1, 2, 3, 4, 5],
            '3:4': [3, 4],
            '1:4,6,8': [1, 2, 3, 4, 6, 8],
            '1,3,7:10,13': [1, 3, 7, 8, 9, 10, 13],
            '1,3:4,7': [1, 3, 4, 7],
        }

        for str_value, arr_value in data.iteritems():
            self.assertEqual(array_from_imap_str(str_value), arr_value)
            self.assertEqual(imap_str_from_sequence(arr_value), str_value)


class IndexSetConversionTest(unittest.TestCase):

    def test_index_set_conversion(self):
        try:
            import AppKit
        except ImportError:
            from nose import SkipTest
            raise SkipTest

        from tinymail.ui_delegates import array_from_index_set
        data = [
            [],
            [0],
            [3],
            [0, 1, 2],
            [7, 8, 9, 22],
        ]

        for value in data:
            index_set = AppKit.NSMutableIndexSet.indexSet()
            for i in value:
                index_set.addIndex_(i)
            converted = array_from_index_set(index_set)
            self.assertEqual(value, converted)
