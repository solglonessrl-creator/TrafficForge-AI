from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .database import supabase
from .storage import read_json, write_json


def _supabase_available() -> bool:
    return supabase is not None


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _utc_date_key() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def get_pageviews_total() -> Dict[str, int]:
    if _supabase_available():
        try:
            res = supabase.table("tf_pageviews").select("path,count").execute()
            rows = getattr(res, "data", None) or []
            return {str(r.get("path")): _safe_int(r.get("count")) for r in rows if isinstance(r, dict) and r.get("path")}
        except Exception:
            pass
    data = read_json("analytics", default={"pageviews": {}, "referrers": {}})
    pageviews = data.get("pageviews") if isinstance(data, dict) and isinstance(data.get("pageviews"), dict) else {}
    return {str(k): _safe_int(v) for k, v in pageviews.items()}


def get_pageviews_today() -> Dict[str, int]:
    date_key = _utc_date_key()
    if _supabase_available():
        try:
            res = supabase.table("tf_pageviews_daily").select("path,count").eq("date", date_key).execute()
            rows = getattr(res, "data", None) or []
            return {str(r.get("path")): _safe_int(r.get("count")) for r in rows if isinstance(r, dict) and r.get("path")}
        except Exception:
            pass
    data = read_json("analytics_daily", default={})
    day = data.get(date_key) if isinstance(data, dict) and isinstance(data.get(date_key), dict) else {}
    return {str(k): _safe_int(v) for k, v in day.items()}


def increment_pageview(path: str) -> None:
    date_key = _utc_date_key()
    if _supabase_available():
        try:
            res = supabase.table("tf_pageviews").select("count").eq("path", path).execute()
            rows = getattr(res, "data", None) or []
            current = _safe_int(rows[0].get("count")) if rows else 0
            supabase.table("tf_pageviews").upsert({"path": path, "count": current + 1}).execute()
        except Exception:
            pass
        try:
            res = (
                supabase.table("tf_pageviews_daily")
                .select("count")
                .eq("date", date_key)
                .eq("path", path)
                .execute()
            )
            rows = getattr(res, "data", None) or []
            current = _safe_int(rows[0].get("count")) if rows else 0
            supabase.table("tf_pageviews_daily").upsert({"date": date_key, "path": path, "count": current + 1}).execute()
            return
        except Exception:
            pass
    data = read_json("analytics", default={"pageviews": {}, "referrers": {}})
    if not isinstance(data, dict):
        data = {"pageviews": {}, "referrers": {}}
    pageviews = data.get("pageviews") if isinstance(data.get("pageviews"), dict) else {}
    pageviews[path] = _safe_int(pageviews.get(path)) + 1
    data["pageviews"] = pageviews
    write_json("analytics", data)

    daily = read_json("analytics_daily", default={})
    if not isinstance(daily, dict):
        daily = {}
    day = daily.get(date_key) if isinstance(daily.get(date_key), dict) else {}
    day[path] = _safe_int(day.get(path)) + 1
    daily[date_key] = day
    write_json("analytics_daily", daily)


def increment_referrer(referrer: str) -> None:
    if _supabase_available():
        try:
            res = supabase.table("tf_referrers").select("count").eq("referrer", referrer).execute()
            rows = getattr(res, "data", None) or []
            current = _safe_int(rows[0].get("count")) if rows else 0
            supabase.table("tf_referrers").upsert({"referrer": referrer, "count": current + 1}).execute()
            return
        except Exception:
            pass
    data = read_json("analytics", default={"pageviews": {}, "referrers": {}})
    if not isinstance(data, dict):
        data = {"pageviews": {}, "referrers": {}}
    referrers = data.get("referrers") if isinstance(data.get("referrers"), dict) else {}
    referrers[referrer] = _safe_int(referrers.get(referrer)) + 1
    data["referrers"] = referrers
    write_json("analytics", data)


def list_posts(status: Optional[str] = None) -> List[Dict[str, Any]]:
    if _supabase_available():
        try:
            q = supabase.table("tf_posts").select("*")
            if status:
                q = q.eq("status", status)
            res = q.execute()
            rows = getattr(res, "data", None) or []
            return [r for r in rows if isinstance(r, dict)]
        except Exception:
            pass
    posts = read_json("posts", default={})
    posts_dict = posts if isinstance(posts, dict) else {}
    items = [p for p in posts_dict.values() if isinstance(p, dict)]
    if status:
        items = [p for p in items if p.get("status") == status]
    return items


def get_post_by_slug(slug: str) -> Optional[Dict[str, Any]]:
    if _supabase_available():
        try:
            res = supabase.table("tf_posts").select("*").eq("slug", slug).limit(1).execute()
            rows = getattr(res, "data", None) or []
            return rows[0] if rows else None
        except Exception:
            pass
    posts = read_json("posts", default={})
    posts_dict = posts if isinstance(posts, dict) else {}
    for p in posts_dict.values():
        if isinstance(p, dict) and p.get("slug") == slug:
            return p
    return None


def upsert_post(post: Dict[str, Any]) -> None:
    if _supabase_available():
        try:
            supabase.table("tf_posts").upsert(post).execute()
            return
        except Exception:
            pass
    posts = read_json("posts", default={})
    posts_dict = posts if isinstance(posts, dict) else {}
    post_id = str(post.get("id") or "")
    if post_id:
        posts_dict[post_id] = post
        write_json("posts", posts_dict)


def list_topics_unused(limit: int) -> List[Dict[str, Any]]:
    if _supabase_available():
        try:
            res = (
                supabase.table("tf_topics")
                .select("*")
                .eq("used", False)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )
            rows = getattr(res, "data", None) or []
            return [r for r in rows if isinstance(r, dict)]
        except Exception:
            pass
    topics = read_json("topics", default={})
    topics_dict = topics if isinstance(topics, dict) else {}
    items = [t for t in topics_dict.values() if isinstance(t, dict) and not t.get("used")]
    return items[:limit]


def upsert_topic(topic: Dict[str, Any]) -> None:
    if _supabase_available():
        try:
            supabase.table("tf_topics").upsert(topic).execute()
            return
        except Exception:
            pass
    topics = read_json("topics", default={})
    topics_dict = topics if isinstance(topics, dict) else {}
    topic_id = str(topic.get("id") or "")
    if topic_id:
        topics_dict[topic_id] = topic
        write_json("topics", topics_dict)


def mark_topic_used(topic_id: str, post_id: str, used_at: str) -> None:
    if _supabase_available():
        try:
            supabase.table("tf_topics").update({"used": True, "used_at": used_at, "post_id": post_id}).eq("id", topic_id).execute()
            return
        except Exception:
            pass
    topics = read_json("topics", default={})
    topics_dict = topics if isinstance(topics, dict) else {}
    if topic_id in topics_dict and isinstance(topics_dict[topic_id], dict):
        topics_dict[topic_id]["used"] = True
        topics_dict[topic_id]["used_at"] = used_at
        topics_dict[topic_id]["post_id"] = post_id
        write_json("topics", topics_dict)


def list_leads() -> List[Dict[str, Any]]:
    if _supabase_available():
        try:
            res = supabase.table("tf_leads").select("*").order("created_at", desc=True).limit(2000).execute()
            rows = getattr(res, "data", None) or []
            return [r for r in rows if isinstance(r, dict)]
        except Exception:
            pass
    leads = read_json("leads", default={})
    leads_dict = leads if isinstance(leads, dict) else {}
    return [l for l in leads_dict.values() if isinstance(l, dict)]


def insert_lead(lead: Dict[str, Any]) -> None:
    if _supabase_available():
        try:
            supabase.table("tf_leads").insert(lead).execute()
            return
        except Exception:
            pass
    leads = read_json("leads", default={})
    leads_dict = leads if isinstance(leads, dict) else {}
    lead_id = str(lead.get("id") or "")
    if lead_id:
        leads_dict[lead_id] = lead
        write_json("leads", leads_dict)


def list_tasks(limit: int = 200) -> List[Dict[str, Any]]:
    if _supabase_available():
        try:
            res = supabase.table("tf_automation_tasks").select("*").order("created_at", desc=True).limit(limit).execute()
            rows = getattr(res, "data", None) or []
            return [r for r in rows if isinstance(r, dict)]
        except Exception:
            pass
    tasks = read_json("automation_tasks", default={})
    tasks_dict = tasks if isinstance(tasks, dict) else {}
    items = [t for t in tasks_dict.values() if isinstance(t, dict)]
    items.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return items[:limit]


def upsert_task(task: Dict[str, Any]) -> None:
    if _supabase_available():
        try:
            supabase.table("tf_automation_tasks").upsert(task).execute()
            return
        except Exception:
            pass
    tasks = read_json("automation_tasks", default={})
    tasks_dict = tasks if isinstance(tasks, dict) else {}
    task_id = str(task.get("id") or "")
    if task_id:
        tasks_dict[task_id] = task
        write_json("automation_tasks", tasks_dict)
