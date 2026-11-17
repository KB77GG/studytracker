import sqlite3,json,time
c=sqlite3.connect("file:/root/apps/studytracker/app.db?mode=ro",uri=True,timeout=0.25)
c.execute("PRAGMA query_only=ON")
allowed={sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_FUNCTION}
c.set_authorizer(lambda a,b,d,e,f:sqlite3.SQLITE_OK if a in allowed else sqlite3.SQLITE_DENY)
start=time.monotonic()
c.set_progress_handler(lambda:int(time.monotonic()-start>3),5000)
queries={"current":"SELECT r.student_id, r.task_id, q.sense_id, q.dimension,\nr.created_at AS at, r.is_correct, r.response_kind,q.score_eligible,q.remediation_kind\nFROM dictation_record AS r JOIN vocabulary_learning_question AS q\nON q.student_id=r.student_id AND q.task_id=r.task_id AND q.first_attempt_id=r.attempt_id\nWHERE r.created_at>=? AND r.created_at<? AND r.is_first_attempt=1 AND q.first_is_correct IS NOT NULL","candidate":"SELECT r.student_id, r.task_id, q.sense_id, q.dimension,\nr.created_at AS at, r.is_correct, r.response_kind,q.score_eligible,q.remediation_kind\nFROM vocabulary_learning_question AS q CROSS JOIN dictation_record AS r\nON q.student_id=r.student_id AND q.task_id=r.task_id AND q.first_attempt_id=r.attempt_id\nWHERE r.created_at>=? AND r.created_at<? AND r.is_first_attempt=1 AND q.first_is_correct IS NOT NULL"}
out={}
for name,query in queries.items():
 out[name]=c.execute("EXPLAIN QUERY PLAN "+query,("2026-10-19 16:00:00","2026-11-16 16:00:00")).fetchall()
out["successful_changes"]=c.total_changes
c.close()
print(json.dumps(out))
