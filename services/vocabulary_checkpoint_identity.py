"""Pure checkpoint identity shared by ORM defaults, scheduling and migration."""

from hashlib import sha256


def checkpoint_selection_key(
    student_id,
    cohort_key,
    sense_id,
    dimension,
    interval_days,
    source_kind="first_correct",
    source_key="initial",
):
    value = f"{student_id}:{cohort_key}:{sense_id}:{dimension}:{interval_days}"
    # Preserve the already-deployed D7/D30 first-correct selection exactly.
    if source_kind != "first_correct" or source_key != "initial":
        value += f":{source_kind}:{source_key}"
    return sha256(value.encode()).hexdigest()


def checkpoint_selection_default(context):
    values = context.get_current_parameters()
    return checkpoint_selection_key(
        values["student_id"],
        values["cohort_key"],
        values["sense_id"],
        values["dimension"],
        values["interval_days"],
        values.get("source_kind") or "first_correct",
        values.get("source_key") or "initial",
    )
