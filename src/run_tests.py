#!/System/Library/Frameworks/Python.framework/Versions/2.6/bin/python2.6

import unittest

test_names = [
    'tinymail.maildata.tests.test_imap',
    'tinymail.maildata.tests.test_account',
    'tinymail.maildata.tests.test_registry',
]

def main():
    load_from = unittest.defaultTestLoader.loadTestsFromName
    suite = unittest.TestSuite(load_from(name) for name in test_names)
    unittest.TextTestRunner().run(suite)

if __name__ == '__main__':
    main()
