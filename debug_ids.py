from app import app
from models import DictationBook, Task

with app.app_context():
    # 1. List all books to find the real ID of 'liu 库 1'
    print("--- All Dictation Books ---")
    books = DictationBook.query.all()
    for b in books:
        print(f"ID: {b.id}, Title: {b.title}, Deleted: {b.is_deleted}, Active: {b.is_active}")

    # 2. Check the Task 178
    print("\n--- Task 178 Detail ---")
    t = Task.query.get(178)
    if t:
        print(f"Task ID: {t.id}")
        print(f"Detail: {t.detail}")
        print(f"DictationBook ID (stored): {t.dictation_book_id}")
    else:
        print("Task 178 not found.")
