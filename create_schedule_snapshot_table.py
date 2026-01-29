from app import app, db
from models import ScheduleSnapshot

with app.app_context():
    print("Creating schedule_snapshot table...")
    db.create_all()
    print("Done!")
