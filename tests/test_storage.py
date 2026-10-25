import os
import pytest
from sorter.storage import Storage

def test_storage_lifecycle(tmp_path):
    db_file = str(tmp_path / "test.db")
    storage = Storage(db_file)
    
    # Verify initial state
    assert not storage.is_processed("college", "<msg1@college.edu>")
    assert storage.get_processed_count() == 0
    
    # Mark as processed
    storage.mark_processed("college", "<msg1@college.edu>", "Urgent Class", True)
    assert storage.is_processed("college", "<msg1@college.edu>")
    assert storage.get_processed_count() == 1
    
    # Separate account with same message_id should not collide
    assert not storage.is_processed("personal", "<msg1@college.edu>")

def test_storage_ensures_directory_exists(tmp_path):
    nested_db = str(tmp_path / "nested" / "dir" / "test.db")
    storage = Storage(nested_db)
    assert os.path.exists(nested_db)
    assert storage.get_processed_count() == 0

def test_storage_mark_processed_idempotent_or_update(tmp_path):
    db_file = str(tmp_path / "test.db")
    storage = Storage(db_file)
    storage.mark_processed("college", "<msg1@college.edu>", "Initial", False)
    assert storage.get_processed_count() == 1
    # Update existing record
    storage.mark_processed("college", "<msg1@college.edu>", "Updated", True)
    assert storage.get_processed_count() == 1
    assert storage.is_processed("college", "<msg1@college.edu>")
