# Legacy Task Migration Guide

This project previously relied on the `Task` / `StudySession` tables.  
After introducing the full study workflow schema you can migrate existing
records into the new tables with the helper script created in this branch.

## Prerequisites

- Ensure the application environment can import the app (virtualenv activated).
- Back up the existing `app.db` (or run on a copy) before executing any script.
- Create at least one teacher/admin account so the migrated plans can be owned.

## Running the migration

```bash
python3 scripts/migrate_legacy.py
```

The script will:

1. Create missing tables defined in `models.py`.
2. Seed `StudentProfile` from distinct legacy task student names.
3. Link students to the teachers/assistants who created their tasks.
4. Create `StudyPlan` per student per day and populate `PlanItem`
   records with the existing task details, durations, and statuses.
5. Generate review logs for tasks that were marked as `done`.

The operation is idempotent — re-running it will skip items already migrated.

## Verification checklist

- Open `/teacher/plans?date=YYYY-MM-DD` for a couple of historical dates and
  confirm the plan items appear for each student.
- Log in as a student and ensure `/student/today` renders the migrated plan.
- Visit `/report` to verify the new data appears in aggregates.
- Optionally, query the database directly:

```sql
SELECT student_id, plan_date, COUNT(*) FROM plan_item
GROUP BY student_id, plan_date
ORDER BY plan_date DESC LIMIT 10;
```

If anything fails, inspect the console output — errors are reported before
the transaction is rolled back.

Always keep the original `Task` data until you have validated the migration. Once
the new workflow is stable you can retire legacy views and tables.
