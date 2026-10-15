"""Name what caused a flagged recent shift, from Perfherder's own alerts.

Pure layer; `fetch_perf_metrics.py` does the requests. The shift is detected on
mozilla-central, but a mozilla-central push is a merge of many autoland pushes
and cannot name a bug. Perfherder alerts on the autoland twin series can: each
alert summary carries the push range the change appeared in -- narrowed when
sheriffs backfill it -- and, once triaged, a linked bug.

The range decides what is said. One push is a landing and its bug is named. A
wide range is only where the test happened to run next; naming the bug in its
last push would blame whichever change was unlucky enough to be tested. That is
not hypothetical: the AV1 1080p encode regression of 2026-10-06 alerted on a
WebRTC ICE fix at the end of a 40-push range.
"""

import re

TREEHERDER = "https://treeherder.mozilla.org"
PERFHERDER_ALERTS = f"{TREEHERDER}/perfherder/alerts"

# Alert summary statuses, per Treeherder's PerformanceAlertSummary model.
SUMMARY_STATUS = {
    0: "untriaged", 1: "downstream", 2: "reassigned", 3: "invalid",
    4: "improvement", 5: "investigating", 6: "wontfix", 7: "fixed",
    8: "backed out",
}
_INVALID = 3
# Per-alert statuses that move an alert to another summary: sheriffs mark an
# alert downstream or reassigned once they find the push really responsible.
_MOVED = (1, 2)

# The autoland alert precedes the mozilla-central run that first shows the
# shift: the merge takes hours, and mozilla-central is tested a few times a day.
ALERT_BEFORE_DAYS = 4
ALERT_AFTER_DAYS = 1

# Ranges are fetched to this many pushes; past it the count is a floor.
PUSH_CAP = 200

_BUG = re.compile(r"\bbug\s+(\d+)", re.IGNORECASE)


def select_alert(summaries, *, signature_id: int, improved: bool,
                 near_ts: float):
    """The (summary, alert) on `signature_id` that explains this shift, or None.

    It must move the same way (an improvement is not explained by a regression
    alert), not be marked invalid, and sit close to the shift's first run. The
    closest wins when several qualify.
    """
    lo = near_ts - ALERT_BEFORE_DAYS * 86400
    hi = near_ts + ALERT_AFTER_DAYS * 86400
    pairs = [
        (s, a) for s in summaries or []
        if s.get("status") != _INVALID and lo <= (s.get("push_timestamp") or 0) <= hi
        for a in s.get("alerts") or []
        if (a.get("series_signature") or {}).get("id") == signature_id
        and a.get("status") != _INVALID
        and bool(a.get("is_regression")) != improved
    ]
    return min(pairs, key=lambda p: abs(p[0]["push_timestamp"] - near_ts),
               default=None)


def alert_redirect(alert: dict):
    """The summary id an alert was moved to, if sheriffs moved it."""
    if alert.get("status") in _MOVED:
        return alert.get("related_summary_id")
    return None


def bugs_in_pushes(pushes) -> list:
    """Bug numbers named in each commit's subject line, in order, once each.

    Only the subject: bodies mention other bugs in passing. Backouts count -- a
    backout changes the build as much as a landing does.
    """
    out = []
    for p in pushes or []:
        for r in p.get("revisions") or []:
            subject = (r.get("comments") or "").split("\n", 1)[0]
            for n in _BUG.findall(subject):
                if int(n) not in out:
                    out.append(int(n))
    return out


def describe_cause(summary: dict, alert: dict, pushes, *,
                   push_cap: int = PUSH_CAP) -> dict:
    """What the page says about the cause. `pushes` is the alert's range.

    A bug is named only when the range is one push with one bug in it, or when
    sheriffs linked one. The push wins over the link.

    `bug_role` says what the named bug is. A push-sourced bug is the landing. A
    linked bug is the landing on an improvement, but on a regression it is the
    tracker sheriffs filed -- and only a tracker's `regressed_by` names the
    cause; a landing's names whatever that landing fixed. `bug_summary` and
    `regressed_by` are filled in by the fetcher from Bugzilla.
    """
    pushes = pushes or []
    bugs = bugs_in_pushes(pushes)
    if len(pushes) == 1 and len(bugs) == 1:
        bug, source, role = bugs[0], "push", "landing"
    elif summary.get("bug_number"):
        bug, source = int(summary["bug_number"]), "alert"
        role = "tracker" if alert.get("is_regression") else "landing"
    else:
        bug, source, role = None, None, None
    return {
        "alert_id": summary.get("id"),
        "alert_url": f"{PERFHERDER_ALERTS}?id={summary.get('id')}",
        "status": SUMMARY_STATUS.get(summary.get("status"), "unknown"),
        "repository": summary.get("repository"),
        "revision": (summary.get("revision") or "")[:12],
        "push_count": len(pushes),
        "push_count_capped": len(pushes) >= push_cap,
        "bug_id": bug,
        "bug_source": source,
        "bug_role": role,
        "bug_summary": None,
        "regressed_by": [],
    }
