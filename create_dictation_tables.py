#!/usr/bin/env python3
"""Create dictation tables in the database."""

from app import app, db
from models import DictationBook, DictationWord, DictationRecord

with app.app_context():
    print("Creating dictation tables...")
    db.create_all()
    print("Done!")
    
    # Verify tables exist
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    tables = inspector.get_table_names()
    
    dictation_tables = ['dictation_book', 'dictation_word', 'dictation_record']
    for table in dictation_tables:
        if table in tables:
            print(f"  ✓ {table} exists")
        else:
            print(f"  ✗ {table} NOT FOUND")
