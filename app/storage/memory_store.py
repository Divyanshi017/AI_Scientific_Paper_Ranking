from collections import Counter
from datetime import datetime, timedelta, timezone
from threading import RLock
from uuid import uuid4

_lock = RLock()

# All data is deliberately held in process memory. It is lost on restart.
papers_by_id = {}
search_history = []
view_events = []

# Anonymized id for the current browser session ("me").
_current_viewer_id: str | None = None


def new_session_id() -> str:
    return uuid4().hex


def current_viewer_id() -> str:
    """Return a stable, anonymized viewer id for this session."""
    global _current_viewer_id
    if _current_viewer_id is None:
        _current_viewer_id = f"viewer_{uuid4().hex[:8]}"
    return _current_viewer_id


def save_search(question: str, papers: list[dict], session_id: str | None = None) -> dict:
    search_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    session_id = session_id or "default"

    with _lock:
        for paper in papers:
            papers_by_id[paper["paper_id"]] = paper

        record = {
            "search_id": search_id,
            "question": question,
            "session_id": session_id,
            "created_at": now,
            "paper_count": len(papers),
            "top_paper_ids": [p["paper_id"] for p in papers[:5]],
        }
        search_history.insert(0, record)
        del search_history[100:]

    return record


def get_papers() -> list[dict]:
    with _lock:
        return list(papers_by_id.values())


def get_search_history(session_id: str | None = None) -> list[dict]:
    with _lock:
        if session_id is None:
            return list(search_history)
        return [record for record in search_history if record.get("session_id") == session_id]


def get_latest_search(session_id: str | None = None) -> dict | None:
    """Latest search for a session (or overall, when session_id is not given)."""
    with _lock:
        if not search_history:
            return None
        record = None
        for candidate in search_history:
            if session_id is None or candidate.get("session_id") == session_id:
                record = candidate
                break
        if record is None:
            return None
        record = dict(record)
        record["papers"] = [
            papers_by_id[pid]
            for pid in record["top_paper_ids"]
            if pid in papers_by_id
        ]
        return record


def record_view(paper_id: str) -> dict:
    with _lock:
        paper = papers_by_id.get(paper_id)
        if not paper:
            raise KeyError("Paper not found in the current in-memory session.")

        viewer = current_viewer_id()
        event = {
            "event_id": str(uuid4()),
            "paper_id": paper_id,
            "viewer_id": viewer,
            "viewed_at": datetime.now(timezone.utc).isoformat(),
        }
        view_events.append(event)
        paper["views"] = int(paper.get("views", 0)) + 1
        viewers = paper.get("viewers", {})
        viewers[viewer] = viewers.get(viewer, 0) + 1
        paper["viewers"] = viewers
        return event


def _view_counts_by_viewer() -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in view_events:
        counts[event["viewer_id"]] = counts.get(event["viewer_id"], 0) + 1
    return counts


def analytics_summary(days: int = 14) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    me = current_viewer_id()
    with _lock:
        recent_events = []
        for event in view_events:
            try:
                viewed_at = datetime.fromisoformat(event["viewed_at"])
            except (TypeError, ValueError):
                continue
            if viewed_at >= cutoff:
                recent_events.append(event)

        viewer_counts = _view_counts_by_viewer()
        my_views = viewer_counts.get(me, 0)
        other_views = sum(v for k, v in viewer_counts.items() if k != me)

        paper_me: dict[str, int] = {}
        paper_others: dict[str, int] = {}
        for event in view_events:
            paper_id = event["paper_id"]
            if event["viewer_id"] == me:
                paper_me[paper_id] = paper_me.get(paper_id, 0) + 1
            else:
                paper_others[paper_id] = paper_others.get(paper_id, 0) + 1

        top_other_ids = [
            paper_id
            for paper_id, _ in sorted(
                paper_others.items(), key=lambda item: item[1], reverse=True
            )[:10]
        ]

        top_papers = []
        for paper_id in top_other_ids:
            paper = papers_by_id.get(paper_id)
            if paper:
                top_papers.append(
                    {
                        "paper_id": paper_id,
                        "title": paper.get("title", "Untitled paper"),
                        "url": paper.get("url", ""),
                        "views_by_others": paper_others.get(paper_id, 0),
                        "views_by_me": paper_me.get(paper_id, 0),
                    }
                )

        all_paper_ids = set(paper_others) | set(paper_me)
        paper_chart = []
        for paper_id in sorted(
            all_paper_ids,
            key=lambda pid: paper_others.get(pid, 0) + paper_me.get(pid, 0),
            reverse=True,
        ):
            paper = papers_by_id.get(paper_id)
            if not paper:
                continue
            viewers = paper.get("viewers", {}) or {}
            paper_chart.append(
                {
                    "paper_id": paper_id,
                    "title": paper.get("title", "Untitled paper"),
                    "views_by_others": paper_others.get(paper_id, 0),
                    "views_by_me": paper_me.get(paper_id, 0),
                    "distinct_readers": len(viewers),
                }
            )

        daily = {}
        for offset in range(days - 1, -1, -1):
            day = (datetime.now(timezone.utc).date() - timedelta(days=offset)).isoformat()
            daily[day] = 0

        for event in recent_events:
            day = datetime.fromisoformat(event["viewed_at"]).date().isoformat()
            if day in daily:
                daily[day] += 1

        return {
            "total_views": len(view_events),
            "views_by_me": my_views,
            "views_by_other_people": other_views,
            "unique_viewers": len(viewer_counts),
            "unique_papers_viewed": len({e["paper_id"] for e in view_events}),
            "papers_in_memory": len(papers_by_id),
            "searches_in_memory": len(search_history),
            "top_papers": top_papers,
            "paper_chart": paper_chart,
            "views_by_day": [{"date": day, "views": count} for day, count in daily.items()],
        }


def clear_memory() -> None:
    """Used by tests and the optional local reset endpoint."""
    with _lock:
        papers_by_id.clear()
        search_history.clear()
        view_events.clear()
        global _current_viewer_id
        _current_viewer_id = None