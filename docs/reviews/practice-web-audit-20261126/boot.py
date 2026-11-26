"""Boot the real app.py against a throwaway SQLite file with synthetic fixtures (no network)."""
import importlib.util, os, sys, tempfile, types, secrets
from datetime import date, timedelta

ROOT = sys.argv[1]
PORT = int(sys.argv[2])
os.chdir(ROOT)
sys.path.insert(0, ROOT)
tmp = tempfile.mkdtemp(prefix="st-audit-")
config = types.ModuleType("config")
config.Config = type("AuditConfig", (), {
    "TESTING": False, "SECRET_KEY": "audit-local-secret",
    "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp}/audit.db",
    "SQLALCHEMY_TRACK_MODIFICATIONS": False, "UPLOAD_FOLDER": tmp,
    "CLASSROOM_PASSCODE": "audit", "SESSION_COOKIE_SECURE": False,
})
sys.modules["config"] = config
spec = importlib.util.spec_from_file_location("audit_app", os.path.join(ROOT, "app.py"))
mod = importlib.util.module_from_spec(spec); sys.modules["audit_app"] = mod
spec.loader.exec_module(mod)
app = mod.app
from models import db, User, StudentProfile, Task
with app.app_context():
    db.create_all()
    t = User(username="audit_teacher", password_hash="x", role=User.ROLE_TEACHER, is_active=True, display_name="王老师")
    a = User(username="audit_assistant", password_hash="x", role=User.ROLE_ASSISTANT, is_active=True, display_name="李助教")
    s = User(username="audit_student", password_hash="x", role=User.ROLE_STUDENT, is_active=True, display_name="测试学生")
    db.session.add_all([t, a, s]); db.session.flush()
    db.session.add(StudentProfile(user_id=s.id, full_name="测试学生"))
    today = date.today().isoformat()
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    rows = [
        Task(date=today, student_name="测试学生", category="听力", detail="剑雅10 Test1 听力", created_by=t.id,
             listening_exercise_id="ielts10_test1", listening_resource_type="cambridge_test", listening_access_token=secrets.token_urlsafe(8)),
        Task(date=today, student_name="测试学生", category="阅读", detail="剑雅10 Test1 阅读", created_by=t.id,
             reading_test_id="ielts10_test1", reading_passage_number=1, reading_access_token=secrets.token_urlsafe(8)),
        Task(date=today, student_name="测试学生", category="精听", detail="精听 剑10 T1 S1", created_by=a.id,
             listening_exercise_id="ielts10_test1_s1", listening_resource_type="intensive", listening_access_token=secrets.token_urlsafe(8)),
        Task(date=tomorrow, student_name="测试学生", category="阅读", detail="剑雅10 Test2 阅读（明天）", created_by=t.id,
             reading_test_id="ielts10_test2", reading_passage_number=2, reading_access_token=secrets.token_urlsafe(8)),
    ]
    db.session.add_all(rows); db.session.commit()
print(f"BOOT_OK db={tmp}/audit.db", flush=True)
app.run(host="127.0.0.1", port=PORT, threaded=True, use_reloader=False, debug=False)
