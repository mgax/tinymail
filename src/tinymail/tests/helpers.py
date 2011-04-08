def mock_db():
    from tinymail.localdata import open_local_db
    return open_local_db(':memory:')
