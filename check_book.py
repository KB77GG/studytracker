from app import app, db
from models import DictationBook

with app.app_context():
    book = DictationBook.query.get(2)
    if book:
        print(f"Book found: ID={book.id}, Title={book.title}, Deleted={book.is_deleted}")
    else:
        print("Book with ID 2 not found.")
