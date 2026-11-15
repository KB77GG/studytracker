"""Pure, conservative integrity state transitions; never controls exam submission."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone

UTC = timezone.utc  # noqa: UP017 -- production supports Python 3.10

EVENT_TYPES = {
    "hello",
    "ack",
    "hidden",
    "visible",
    "heartbeat",
    "blur",
    "viewport",
    "copy_blocked",
    "paste_blocked",
}
SECTIONS = {"process", "intro", "listening", "reading", "writing", "finished"}


def as_utc(now=None):
    value = now or datetime.utcnow()
    # Python 3.10 production compatibility (datetime.UTC was added in 3.11).
    return value.astimezone(UTC).replace(tzinfo=None) if value.tzinfo else value


def timestamp(value):
    return value.isoformat(timespec="milliseconds") + "Z" if value else None


def finite_number(value, maximum=1e15):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value) if math.isfinite(value) and 0 <= value <= maximum else None


def device_hash(device_id):
    if not isinstance(device_id, str) or not 8 <= len(device_id) <= 160:
        return None
    return hashlib.sha256(device_id.encode("utf-8")).hexdigest()


def safe_detail(payload):
    """Do not persist clipboard text, user agent, tokens, or arbitrary client data."""
    raw = payload.get("detail")
    raw = raw if isinstance(raw, dict) else {}
    detail = {}
    for key in ("length", "ratio", "width", "screen_width"):
        number = finite_number(raw.get(key), 1_000_000)
        if number is not None:
            detail[key] = number
    if isinstance(raw.get("blocked"), bool):
        detail["blocked"] = raw["blocked"]
    if raw.get("signal") in {"paste", "drop", "beforeinput", "copy", "cut"}:
        detail["signal"] = raw["signal"]
    return json.dumps(detail, separators=(",", ":"), ensure_ascii=False)


def clear_hidden(state, discard=False):
    if discard and state.hidden_page_id:
        state.discard_visible_page_id = state.hidden_page_id
    state.hidden_at = state.hidden_page_id = state.hidden_section = None
    state.hidden_client_ts = None


def can_enforce(state, policy, section):
    return policy["mode"] == "enforce" and not state.exempt and section in {"reading", "writing"}


def maybe_lock(state, policy, section, now):
    if state.is_locked or not can_enforce(state, policy, section):
        return False
    if state.unlocked_at:
        count_due = state.leave_count - state.unlock_leave_count >= 1
        duration_due = state.hidden_seconds - state.unlock_hidden_seconds >= 30
    else:
        count_due = state.leave_count >= policy["max_leaves"]
        duration_due = state.hidden_seconds >= policy["max_hidden_seconds"]
    if not count_due and not duration_due:
        return False
    state.is_locked = True
    state.locked_at = now
    state.locked_section = section
    state.locked_reason = "离开次数达到上限" if count_due else "累计离开时间达到上限"
    return True


def _finish_hidden(state, now, minimum, section):
    duration = max(0.0, (now - state.hidden_at).total_seconds())
    if duration >= minimum:
        state.leave_count += 1
        state.hidden_seconds += duration
    clear_hidden(state)
    return duration


def _visible(state, payload, now, section, page_id, active):
    if state.current_page_id != page_id:
        return None
    client_ts = finite_number(payload.get("client_ts"))
    if client_ts is not None and state.last_visible_client_ts is not None:
        if client_ts <= state.last_visible_client_ts:
            return None
    duration = None
    if (
        state.hidden_page_id == page_id
        and state.hidden_client_ts is not None
        and client_ts is not None
        and client_ts < state.hidden_client_ts
    ):
        # A delayed return from a previous interval must not close a newer hide.
        return None
    if state.discard_visible_page_id == page_id:
        state.discard_visible_page_id = None
        clear_hidden(state)
        if client_ts is not None:
            state.last_visible_client_ts = client_ts
        return None
    if state.hidden_at and state.hidden_page_id == page_id:
        if state.current_page_id != page_id or state.current_section != section:
            return None
        if state.hidden_section == section and active:
            duration = _finish_hidden(state, now, 2, section)
        else:
            clear_hidden(state)
    elif not state.hidden_at and active and state.current_page_id == page_id:
        # Beacon loss: bounded client duration is only a fallback, never added twice.
        duration_ms = finite_number(payload.get("client_hidden_ms"), 86_400_000)
        if duration_ms is not None and client_ts is not None and duration_ms >= 2000:
            duration = duration_ms / 1000
            state.leave_count += 1
            state.hidden_seconds += duration
    if client_ts is not None:
        state.last_visible_client_ts = client_ts
    return duration


def transition(
    state,
    policy,
    payload,
    *,
    now=None,
    current_section=None,
    submitted_sections=(),
    active_sections=None,
):
    """Mutate only the supplied integrity state; return log descriptions."""
    now = as_utc(now)
    event_type = payload.get("type")
    if event_type not in EVENT_TYPES:
        raise ValueError("invalid_event_type")
    section = payload.get("section", "process")
    if section not in SECTIONS:
        raise ValueError("invalid_section")
    page_id = payload.get("page_id")
    if not isinstance(page_id, str) or not 1 <= len(page_id) <= 96:
        raise ValueError("invalid_page_id")
    logs = []
    incoming_hash = device_hash(payload.get("device_id"))
    enforce_device = policy["mode"] == "enforce" and not state.exempt
    if (
        enforce_device
        and state.device_hash
        and incoming_hash
        and incoming_hash != state.device_hash
    ):
        state.device_conflict_count += 1
        state.device_conflict_at = now
        return [{"type": "device_conflict", "section": section}]
    if event_type == "hello" and enforce_device and incoming_hash and not state.device_hash:
        state.device_hash = incoming_hash
    sections = {"listening", "reading", "writing"}
    unfinished = sections - set(submitted_sections)
    if active_sections is not None:
        unfinished &= set(active_sections)
    active = section in unfinished
    active = active and (current_section is None or current_section == section)
    # Only queued visibility events use an elapsed delay. Client wall clocks may
    # differ from the server; the browser reports time held in its memory queue.
    delay_ms = finite_number(payload.get("queued_ms"), 86_400_000)
    occurred_at = now
    if event_type in {"hidden", "visible"} and delay_ms is not None:
        occurred_at -= timedelta(milliseconds=delay_ms)
    leaves_before = state.leave_count
    duration = None
    if event_type == "hello":
        completed_page = None
        completed_client_ts = None
        on_process = section in {"process", "intro"}
        prior_active = state.current_section in unfinished
        if on_process and prior_active and not state.hidden_at:
            # Navigating within the exam may not dispatch visibilitychange.
            # A started, unfinished section is still running on the chapter page.
            state.hidden_at = now
            state.hidden_page_id = state.current_page_id
            state.hidden_section = state.current_section
            state.hidden_client_ts = None
        if state.hidden_at:
            preserve = on_process and state.hidden_section in unfinished
            returning = state.hidden_page_id != page_id or state.current_section in {
                "process",
                "intro",
            }
            if not preserve and returning and active and state.hidden_section == section:
                completed_page = state.hidden_page_id
                completed_client_ts = state.hidden_client_ts
                duration = _finish_hidden(state, now, 10, section)
            elif not preserve and (returning or state.hidden_section not in unfinished):
                clear_hidden(state)
        if state.current_page_id != page_id:
            state.last_visible_client_ts = None
            state.discard_visible_page_id = None
        if completed_page:
            # A queued old visible may arrive after hello already settled the
            # interval, including a bfcache return to the same page ID.
            state.discard_visible_page_id = completed_page
            if completed_page == page_id:
                # The original hidden may also be queued after a successful
                # beacon. Settling on a bfcache hello must consume that replay.
                candidates = [
                    value
                    for value in (completed_client_ts, finite_number(payload.get("client_ts")))
                    if value is not None
                ]
                state.last_visible_client_ts = max(candidates) if candidates else None
        state.current_page_id, state.current_section = page_id, section
    elif event_type == "ack":
        state.acked_at = now
    elif event_type == "hidden" and active:
        if not state.current_page_id:
            state.current_page_id, state.current_section = page_id, section
        client_ts = finite_number(payload.get("client_ts"))
        late = (
            client_ts is not None
            and state.last_visible_client_ts is not None
            and client_ts <= state.last_visible_client_ts
        )
        if not state.hidden_at and state.current_page_id == page_id and not late:
            state.discard_visible_page_id = None
            state.hidden_at, state.hidden_page_id, state.hidden_section = (
                occurred_at,
                page_id,
                section,
            )
            state.hidden_client_ts = client_ts
    elif event_type == "visible":
        duration = _visible(state, payload, occurred_at, section, page_id, active)
    elif event_type == "heartbeat" and state.last_seen_at and not state.hidden_at:
        gap = max(0, (now - state.last_seen_at).total_seconds())
        if gap > 60:
            logs.append({"type": "heartbeat_gap", "section": section, "duration_seconds": gap})
    elif event_type == "blur":
        state.blur_count += 1
    elif event_type in {"copy_blocked", "paste_blocked"}:
        stem = "copy" if event_type == "copy_blocked" else "paste"
        attempts = f"{stem}_attempt_count"
        setattr(state, attempts, getattr(state, attempts) + 1)
        detail = payload.get("detail")
        if (
            policy["mode"] == "enforce"
            and not state.exempt
            and isinstance(detail, dict)
            and detail.get("blocked") is True
        ):
            field = f"{stem}_blocked_count"
            setattr(state, field, getattr(state, field) + 1)
    if event_type != "hidden":
        state.last_seen_at = now
    if event_type != "heartbeat":
        logs.append(
            {
                "type": event_type,
                "section": section,
                "duration_seconds": duration,
                "question_ref": str(payload.get("question") or "")[:64],
                "client_ts": str(payload.get("client_ts") or "")[:64],
                "detail_json": safe_detail(payload),
            }
        )
    if state.leave_count > leaves_before:
        logs.append({"type": "leave", "section": section, "duration_seconds": duration})
    # Never lock due to a stale page, a heartbeat, blur, or a short visibility flap.
    if active and duration is not None and duration >= (10 if event_type == "hello" else 2):
        if maybe_lock(state, policy, section, now):
            logs.append({"type": "locked", "section": section})
    return logs


def serialize(state, policy, *, device_id="", section=None, now=None):
    now = as_utc(now)
    result = dict(policy)
    result.update(
        ok=True,
        enabled=policy["mode"] != "off",
        acked=False,
        acked_at=None,
        is_locked=False,
        device_conflict=False,
        device_bound=False,
        exempt=False,
        leave_count=0,
        hidden_seconds=0,
        blur_count=0,
        copy_attempt_count=0,
        paste_attempt_count=0,
        copy_blocked_count=0,
        paste_blocked_count=0,
        device_conflict_count=0,
        unlock_count=0,
        locked_reason=None,
        locked_at=None,
        locked_section=None,
        last_seen_at=None,
        hidden_at=None,
        current_section=section or "process",
        stale=False,
        risk="low",
    )
    if state is None:
        return result
    for field in (
        "leave_count",
        "hidden_seconds",
        "blur_count",
        "copy_attempt_count",
        "paste_attempt_count",
        "copy_blocked_count",
        "paste_blocked_count",
        "device_conflict_count",
        "unlock_count",
        "locked_reason",
        "locked_section",
        "exempt",
        "current_section",
    ):
        result[field] = getattr(state, field)
    for field in ("acked_at", "last_seen_at", "hidden_at", "locked_at", "unlocked_at"):
        result[field] = timestamp(getattr(state, field))
    result["state_id"], result["session_ref"] = state.id, state.session_ref
    result["acked"] = bool(state.acked_at)
    result["device_bound"] = bool(state.device_hash)
    requested_section = section or state.current_section
    result["is_locked"] = bool(state.is_locked and can_enforce(state, policy, requested_section))
    incoming = device_hash(device_id)
    result["device_conflict"] = bool(
        policy["mode"] == "enforce"
        and not state.exempt
        and incoming
        and state.device_hash
        and incoming != state.device_hash
    )
    result["has_device_conflict"] = bool(state.device_conflict_at)
    result["stale"] = bool(state.last_seen_at and (now - state.last_seen_at).total_seconds() > 60)
    result["risk"] = (
        "high"
        if state.locked_at or state.device_conflict_count or state.paste_blocked_count
        else "medium" if state.leave_count else "low"
    )
    return result
