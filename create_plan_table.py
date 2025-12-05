from app import app, db
from models import CoursePlan

with app.app_context():
    print("Creating course_plan table...")
    db.create_all()
    print("Done!")
