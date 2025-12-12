from app import app
from models import DictationBook, MaterialBank, Question

print("Imports successful.")

try:
    with app.app_context():
        print("Checking DictationBook query...")
        books = DictationBook.query.all()
        print(f"Found {len(books)} books")
        for b in books:
            print(f"Book: {b.title}, Word Count: {b.word_count}")

        print("Checking MaterialBank query...")
        materials = MaterialBank.query.filter_by(is_deleted=False, is_active=True).all()
        print(f"Found {len(materials)} materials")
        
        from models import Task, PlanItem, StudyPlan
        from sqlalchemy.orm import joinedload
        
        print("Checking Task query...")
        tasks = Task.query.limit(5).all()
        print(f"Found {len(tasks)} tasks")
        
        # Simulate the loop in tasks_page
        all_materials = []
        for m in materials:
            question_count = Question.query.filter_by(material_id=m.id).count()
            all_materials.append({
                "id": m.id,
                "title": m.title,
                "question_count": f"{question_count}题"
            })
        
        for book in books:
             all_materials.append({
                "id": f"dictation-{book.id}",
                "title": book.title,
                "question_count": f"{book.word_count}词"
            })
            
        print("Checking Pending Items query...")
        try:
            pending_items_query = PlanItem.query.filter(
                PlanItem.review_status == PlanItem.REVIEW_PENDING,
                PlanItem.student_status == PlanItem.STUDENT_SUBMITTED,
                PlanItem.is_deleted.is_(False),
                PlanItem.plan.has(StudyPlan.is_deleted.is_(False)),
            ).options(
                joinedload(PlanItem.plan).joinedload(StudyPlan.student),
            ).all()
            print(f"Found {len(pending_items_query)} pending items")
        except Exception as e:
            print(f"Error in pending items query: {e}")
            
        print(f"Successfully constructed {len(all_materials)} items.")
        
        # Test Template Rendering
        print("Testing template rendering...")
        from flask import render_template_string, url_for, get_flashed_messages
        import os
        
        # Read template
        with open('templates/tasks.html', 'r') as f:
            template_content = f.read()
            
        # Mock context
        context = {
            "all_materials": all_materials,
            "period": "week",
            "stats": {"total":0, "completed":0, "total_minutes": 0, "avg_accuracy": 0.0},
            "recent_tasks": [],
            "top_students": [],
            "today": "2025-12-12",
            "all_students": ["Student A"],
            "student_names": ["Student A"],
            "items": [],
            "pending_reviews": [],
            "current_user": type('User', (object,), {'is_authenticated': True, 'role': 'teacher', 'display_name': 'Teacher', 'username': 'teacher'})()
        }
        
        # Needed for url_for to work (dummy request context or mock)
        with app.test_request_context('/tasks'):
             # We need to mock base.html extension? render_template_string treats it as standalone if no extends?
             # But tasks.html extends base.html.
             # So we should use render_template if possible, but app needs to accept the path.
             pass
             
        # Actually easier to use app.jinja_env
        print("rendering check...")
        # Since it extends base.html, we need full environment.
        try:
            with app.test_request_context('/tasks'):
                from flask import render_template
                # We can call render_template directly
                render_template("tasks.html", **context)
                print("Template rendered successfully!")
        except Exception as e:
            print(f"Template rendering failed: {e}")
            import traceback
            traceback.print_exc()
            
except Exception as e:
    print(f"Error caught: {e}")
    import traceback
    traceback.print_exc()
