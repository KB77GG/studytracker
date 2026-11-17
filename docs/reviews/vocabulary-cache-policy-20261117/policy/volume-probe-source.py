import sqlite3,json,time
c=sqlite3.connect("file:/root/apps/studytracker/app.db?mode=ro",uri=True,timeout=1)
c.execute("PRAGMA query_only=ON")
allowed={sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_FUNCTION}
c.set_authorizer(lambda a,b,d,e,f: sqlite3.SQLITE_OK if a in allowed else sqlite3.SQLITE_DENY)
start=time.monotonic()
c.set_progress_handler(lambda: int(time.monotonic()-start>5),10000)
out={}
for table,col in (("vocabulary_learning_flow","started_at"),("vocabulary_learning_question","created_at"),("vocabulary_review_attempt","submitted_at"),("vocabulary_review_settlement","settled_at"),("student_vocabulary_mastery","created_at")):
    out[table]=dict(zip(("rows","earliest","latest"),c.execute("SELECT COUNT(*), MIN("+col+"), MAX("+col+") FROM "+table).fetchone()))
out["elapsed_s"]=round(time.monotonic()-start,3)
out["total_changes"]=c.total_changes
c.close()
print(json.dumps(out))
