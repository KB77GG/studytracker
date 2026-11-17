import importlib.util,json,time
from pathlib import Path
from datetime import datetime
from itertools import islice
from contextlib import closing
root=Path("/root/apps/studytracker")
spec=importlib.util.spec_from_file_location("readonly_entry_verifier",root/"docs/reviews/miniprogram-entry-20261116/verify_production_entry.py")
v=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
cases=v.select_cases(root/"app.db",Path("/var/log/nginx"))
observations=[]
app=v.make_readonly_app(root,root/"app.db",observations)
from models import User,db
from services.vocabulary_autonomous_review import _iter_due_candidates
out=[]
for label,user_id,_task_id in cases:
    with app.app_context():
        db.session.autoflush=False
        raw=db.session.connection().connection.driver_connection
        raw.execute("BEGIN")
        try:
            user=db.session.get(User,user_id)
            started=time.perf_counter()
            with closing(_iter_due_candidates(user,datetime.utcnow())) as candidates:
                rows=list(islice(candidates,20))
            out.append({"case":label,"sample_size":len(rows),"elapsed_ms":round((time.perf_counter()-started)*1000,3),"query_only":raw.execute("PRAGMA query_only").fetchone()[0]==1,"total_changes_zero":raw.total_changes==0,"no_pending_orm":not(db.session.new or db.session.dirty or db.session.deleted)})
        finally:
            db.session.rollback()
            db.session.remove()
print(json.dumps({"read_only_finite_selection":True,"real_claim_executed":False,"cases":out,"blocked_sql_attempts":sum(x["blocked"] for x in observations)}))
