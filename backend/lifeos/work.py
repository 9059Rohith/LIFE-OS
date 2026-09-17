"""Owner-scoped work records and statistics derived from saved history."""

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import HTTPException, Request
from pydantic import Field, ValidationError, field_validator

from .schemas import Strict
from .store import digest, uid


class Named(Strict):
    title: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=4000)

    @field_validator("title")
    @classmethod
    def nonblank_title(cls, value):
        if not value.strip():
            raise ValueError("Title cannot be blank")
        return value.strip()


class ProjectFields(Named):
    status: Literal["active", "completed", "archived"] = "active"


class GoalFields(Named):
    status: Literal["active", "completed", "archived"] = "active"
    target_date: str | None = None
    project_id: str | None = None

    @field_validator("target_date")
    @classmethod
    def valid_target_date(cls, value):
        if value is not None:
            date.fromisoformat(value)
        return value


class TaskFields(Named):
    status: Literal["todo", "doing", "done"] = "todo"
    priority: Literal["low", "medium", "high"] = "medium"
    due_date: str | None = None
    project_id: str | None = None
    goal_id: str | None = None

    @field_validator("due_date")
    @classmethod
    def valid_due_date(cls, value):
        if value is not None:
            date.fromisoformat(value)
        return value


class HabitFields(Named):
    frequency: Literal["daily", "weekly"] = "daily"
    target_per_week: int = Field(default=1, ge=1, le=7)
    archived: bool = False
    project_id: str | None = None
    goal_id: str | None = None


class NoteFields(Strict):
    title: str = Field(min_length=1, max_length=160)
    body: str = Field(min_length=1, max_length=20000)
    project_id: str | None = None
    goal_id: str | None = None
    task_id: str | None = None

    @field_validator("title", "body")
    @classmethod
    def nonblank_text(cls, value):
        if not value.strip():
            raise ValueError("Text cannot be blank")
        return value.strip()


class CheckinInput(Strict):
    day: str

    @field_validator("day")
    @classmethod
    def valid_day(cls, value):
        date.fromisoformat(value)
        return value


SCHEMAS = {
    "projects": ProjectFields,
    "goals": GoalFields,
    "tasks": TaskFields,
    "habits": HabitFields,
    "notes": NoteFields,
}


def kind_for(value):
    if value not in SCHEMAS:
        raise HTTPException(404, "Unknown workspace collection")
    return "work_" + value


def validate(schema, payload):
    try:
        return schema.model_validate(payload).model_dump()
    except ValidationError as exc:
        raise HTTPException(422, exc.errors(include_input=False, include_context=False)) from None
    except ValueError:
        raise HTTPException(422, "Invalid date") from None


def effective_project(item, goals):
    if item.get("project_id"):
        return item["project_id"]
    goal = goals.get(item.get("goal_id"))
    return goal.get("project_id") if goal else None


def habit_streak(habit, days, today):
    dates = {date.fromisoformat(day) for day in days}
    if not dates:
        return 0
    if habit["frequency"] == "daily":
        cursor = today if today in dates else today - timedelta(days=1)
        streak = 0
        while cursor in dates:
            streak += 1
            cursor -= timedelta(days=1)
        return streak
    week = today - timedelta(days=today.weekday())
    target = habit["target_per_week"]
    if sum(week <= day < week + timedelta(days=7) for day in dates) < target:
        week -= timedelta(days=7)
    streak = 0
    while sum(week <= day < week + timedelta(days=7) for day in dates) >= target:
        streak += 1
        week -= timedelta(days=7)
    return streak


def register_work(app, db, security, engine):
    def record_activity(owner, collection, item_id, action):
        item = {"id": uid(), "collection": collection, "item_id": item_id,
                "action": action, "at": datetime.now(UTC).isoformat()}
        db.put(owner, "work_activity", item["id"], item)

    def get_item(owner, collection, item_id):
        item = db.get(owner, kind_for(collection), item_id)
        if not item:
            raise HTTPException(404, "Workspace item not found")
        return item

    def notifications_for(owner):
        today = datetime.now(ZoneInfo(engine.settings_for(owner)["timezone"])).date().isoformat()
        checked = {(item["habit_id"], item["day"]) for item in db.list(owner, "habit_checkin")}
        acknowledged = {item["id"] for item in db.list(owner, "work_notification_ack")}
        notices = []
        for task in db.list(owner, "work_tasks"):
            due = task.get("due_date")
            if task["status"] == "done" or not due or due > today:
                continue
            category = "task_overdue" if due < today else "task_due"
            identifier = digest([category, task["id"], today])
            if identifier not in acknowledged:
                notices.append({"id": identifier, "category": category, "item_id": task["id"],
                                "title": task["title"], "date": due})
        for habit in db.list(owner, "work_habits"):
            if habit["archived"] or habit["frequency"] != "daily" or (habit["id"], today) in checked:
                continue
            identifier = digest(["habit_due", habit["id"], today])
            if identifier not in acknowledged:
                notices.append({"id": identifier, "category": "habit_due", "item_id": habit["id"],
                                "title": habit["title"], "date": today})
        return notices

    def check_links(owner, collection, fields):
        for link, target in (("project_id", "projects"), ("goal_id", "goals"), ("task_id", "tasks")):
            linked_id = fields.get(link)
            if linked_id:
                get_item(owner, target, linked_id)
        if fields.get("goal_id") and fields.get("project_id"):
            goal = get_item(owner, "goals", fields["goal_id"])
            if goal.get("project_id") and goal["project_id"] != fields["project_id"]:
                raise HTTPException(422, "Goal and project links disagree")
        if collection == "notes" and fields.get("task_id"):
            task = get_item(owner, "tasks", fields["task_id"])
            if fields.get("goal_id") and task.get("goal_id") and fields["goal_id"] != task["goal_id"]:
                raise HTTPException(422, "Task and goal links disagree")
            if fields.get("project_id"):
                task_goal = get_item(owner, "goals", task["goal_id"]) if task.get("goal_id") else None
                task_project = effective_project(task, {task_goal["id"]: task_goal} if task_goal else {})
                if task_project and fields["project_id"] != task_project:
                    raise HTTPException(422, "Task and project links disagree")

    def summary_for(owner):
        projects = db.list(owner, "work_projects")
        goals = db.list(owner, "work_goals")
        tasks = db.list(owner, "work_tasks")
        habits = db.list(owner, "work_habits")
        notes = db.list(owner, "work_notes")
        checkins = db.list(owner, "habit_checkin")
        goal_map = {item["id"]: item for item in goals}
        timezone = ZoneInfo(engine.settings_for(owner)["timezone"])
        today = datetime.now(timezone).date()
        first_day = today - timedelta(days=13)
        activity = db.list_since(owner, "work_activity", datetime.combine(first_day, time.min, timezone).timestamp())
        daily = {str(first_day + timedelta(days=step)): 0 for step in range(14)}
        for entry in activity:
            day = datetime.fromisoformat(entry["at"]).astimezone(timezone).date().isoformat()
            if day in daily:
                daily[day] += 1
        days_by_habit = {}
        for item in checkins:
            days_by_habit.setdefault(item["habit_id"], []).append(item["day"])
        goal_counts = defaultdict(lambda: [0, 0])
        project_counts = defaultdict(lambda: [0, 0])
        for task in tasks:
            done = int(task["status"] == "done")
            if task.get("goal_id"):
                goal_counts[task["goal_id"]][0] += 1
                goal_counts[task["goal_id"]][1] += done
            project_id = effective_project(task, goal_map)
            if project_id:
                project_counts[project_id][0] += 1
                project_counts[project_id][1] += done
        goal_progress = [{"id": goal["id"], "total": goal_counts[goal["id"]][0],
                          "completed": goal_counts[goal["id"]][1]} for goal in goals]
        project_progress = [{"id": project["id"], "total": project_counts[project["id"]][0],
                             "completed": project_counts[project["id"]][1]} for project in projects]
        return {
            "projects": len(projects), "goals": len(goals), "tasks": len(tasks),
            "tasks_completed": sum(task["status"] == "done" for task in tasks),
            "tasks_due_today": sum(task["status"] != "done" and task.get("due_date") == today.isoformat() for task in tasks),
            "habits": len(habits), "notes": len(notes),
            "checkins": len(checkins),
            "activity_days": [{"day": day, "count": count} for day, count in daily.items()],
            "goal_progress": goal_progress,
            "project_progress": project_progress,
            "habit_streaks": [{
                "id": habit["id"], "streak": habit_streak(habit, days_by_habit.get(habit["id"], []), today),
            } for habit in habits if not habit["archived"]],
        }

    @app.get("/api/work/summary")
    def summary(request: Request):
        return summary_for(security.require(request))

    @app.get("/api/work/calendar")
    def calendar(request: Request, days: int = 14):
        owner = security.require(request)
        if days < 1 or days > 31:
            raise HTTPException(422, "Calendar range must be 1–31 days")
        timezone = ZoneInfo(engine.settings_for(owner)["timezone"])
        today = datetime.now(timezone).date()
        last = today + timedelta(days=days - 1)
        items = []
        for task in db.list(owner, "work_tasks"):
            due = task.get("due_date")
            if due and today <= date.fromisoformat(due) <= last:
                items.append({"id": task["id"], "date": due, "title": task["title"],
                              "kind": "task", "status": task["status"], "project_id": task.get("project_id"),
                              "goal_id": task.get("goal_id")})
        for goal in db.list(owner, "work_goals"):
            target = goal.get("target_date")
            if target and today <= date.fromisoformat(target) <= last:
                items.append({"id": goal["id"], "date": target, "title": goal["title"],
                              "kind": "goal", "status": goal["status"], "project_id": goal.get("project_id")})
        return {"start": today.isoformat(), "end": last.isoformat(),
                "items": sorted(items, key=lambda item: (item["date"], item["title"], item["id"]))}

    @app.get("/api/work/notifications")
    def notifications(request: Request):
        return notifications_for(security.require(request))

    @app.post("/api/work/notifications/{notice_id}/dismiss")
    def dismiss_notification(notice_id: str, request: Request):
        owner = security.require(request, True)
        if not any(item["id"] == notice_id for item in notifications_for(owner)):
            raise HTTPException(404, "Notification not found")
        db.put(owner, "work_notification_ack", notice_id, {"id": notice_id,
               "dismissed_at": datetime.now(UTC).isoformat()})
        return {"status": "dismissed"}

    def page_for(owner, collection, offset, limit):
        if offset < 0 or limit < 1 or limit > 100:
            raise HTTPException(422, "Invalid pagination")
        items, total = db.list_page(owner, kind_for(collection), offset, limit)
        if collection == "habits":
            checkins = db.list(owner, "habit_checkin")
            by_habit = {}
            for item in checkins:
                by_habit.setdefault(item["habit_id"], []).append(item["day"])
            today = datetime.now(ZoneInfo(engine.settings_for(owner)["timezone"])).date()
            items = [{**item, "checkins": by_habit.get(item["id"], []),
                      "streak": habit_streak(item, by_habit.get(item["id"], []), today)} for item in items]
        return {"items": items, "total": total, "offset": offset, "limit": limit}

    @app.get("/api/work/dashboard")
    def dashboard(request: Request, collection: str = "tasks", offset: int = 0, limit: int = 20):
        owner = security.require(request)
        kind_for(collection)
        return {
            "page": page_for(owner, collection, offset, limit),
            "summary": summary_for(owner),
            "links": {
                group: [{"id": item["id"], "title": item["title"]}
                        for item in db.list(owner, kind_for(group))]
                for group in ("projects", "goals", "tasks")
            },
            "timezone": engine.settings_for(owner)["timezone"],
            "notifications": notifications_for(owner),
        }

    @app.get("/api/work/{collection}")
    def list_items(collection: str, request: Request, offset: int = 0, limit: int = 50):
        return page_for(security.require(request), collection, offset, limit)

    @app.post("/api/work/{collection}")
    def create_item(collection: str, payload: dict, request: Request):
        owner = security.require(request, True)
        kind = kind_for(collection)
        fields = validate(SCHEMAS[collection], payload)
        check_links(owner, collection, fields)
        now = datetime.now(UTC).isoformat()
        item = {"id": uid(), "kind": collection, **fields, "created_at": now, "updated_at": now}
        if collection == "tasks":
            item["completed_at"] = now if fields["status"] == "done" else None
        db.put(owner, kind, item["id"], item)
        record_activity(owner, collection, item["id"], "created")
        db.audit(owner, "work_created", f"{collection[:-1]} created", details={"item_id": item["id"], "kind": collection})
        return item

    @app.patch("/api/work/{collection}/{item_id}")
    def update_item(collection: str, item_id: str, payload: dict, request: Request):
        owner = security.require(request, True)
        item = get_item(owner, collection, item_id)
        schema = SCHEMAS[collection]
        if not payload or set(payload) - set(schema.model_fields):
            raise HTTPException(422, "No valid changes supplied")
        fields = validate(schema, {key: payload.get(key, item.get(key)) for key in schema.model_fields})
        check_links(owner, collection, fields)
        now = datetime.now(UTC).isoformat()
        updated = {**item, **fields, "updated_at": now}
        if collection == "tasks" and fields["status"] != item["status"]:
            updated["completed_at"] = now if fields["status"] == "done" else None
        db.put(owner, kind_for(collection), item_id, updated)
        record_activity(owner, collection, item_id,
                        "completed" if collection == "tasks" and item["status"] != "done" and fields["status"] == "done" else "updated")
        db.audit(owner, "work_updated", f"{collection[:-1]} updated", details={"item_id": item_id, "kind": collection})
        return updated

    @app.delete("/api/work/{collection}/{item_id}")
    def delete_item(collection: str, item_id: str, request: Request):
        owner = security.require(request, True)
        get_item(owner, collection, item_id)
        children = {
            "projects": [("goals", "project_id"), ("tasks", "project_id"), ("habits", "project_id"), ("notes", "project_id")],
            "goals": [("tasks", "goal_id"), ("habits", "goal_id"), ("notes", "goal_id")],
            "tasks": [("notes", "task_id")],
        }.get(collection, [])
        if any(any(child.get(link) == item_id for child in db.list(owner, kind_for(group))) for group, link in children):
            raise HTTPException(409, "Move or delete linked items first")
        if collection == "habits":
            for checkin in db.list(owner, "habit_checkin"):
                if checkin["habit_id"] == item_id:
                    db.delete(owner, "habit_checkin", checkin["id"])
        db.delete(owner, kind_for(collection), item_id)
        record_activity(owner, collection, item_id, "deleted")
        db.audit(owner, "work_deleted", f"{collection[:-1]} deleted", details={"item_id": item_id, "kind": collection})
        return {"status": "deleted"}

    @app.post("/api/work/habits/{habit_id}/checkins")
    def add_checkin(habit_id: str, body: CheckinInput, request: Request):
        owner = security.require(request, True)
        habit = get_item(owner, "habits", habit_id)
        if habit["archived"]:
            raise HTTPException(409, "Archived habits cannot be checked in")
        today = datetime.now(ZoneInfo(engine.settings_for(owner)["timezone"])).date()
        day = date.fromisoformat(body.day)
        if day > today or day < today - timedelta(days=365):
            raise HTTPException(422, "Check-in date must be within the past year")
        checkin_id = f"{owner}:habit:{habit_id}:{body.day}"
        existing = db.get(owner, "habit_checkin", checkin_id)
        if existing:
            return existing
        item = {"id": checkin_id, "habit_id": habit_id, "day": body.day,
                "created_at": datetime.now(UTC).isoformat()}
        db.put(owner, "habit_checkin", checkin_id, item)
        record_activity(owner, "habits", habit_id, "checked_in")
        db.audit(owner, "habit_checked", "Habit checked in", details={"habit_id": habit_id, "day": body.day})
        return item

    @app.delete("/api/work/habits/{habit_id}/checkins/{day}")
    def remove_checkin(habit_id: str, day: str, request: Request):
        owner = security.require(request, True)
        get_item(owner, "habits", habit_id)
        try:
            date.fromisoformat(day)
        except ValueError:
            raise HTTPException(422, "Invalid date") from None
        checkin_id = f"{owner}:habit:{habit_id}:{day}"
        if not db.get(owner, "habit_checkin", checkin_id):
            raise HTTPException(404, "Check-in not found")
        db.delete(owner, "habit_checkin", checkin_id)
        record_activity(owner, "habits", habit_id, "checkin_removed")
        db.audit(owner, "habit_unchecked", "Habit check-in removed", details={"habit_id": habit_id, "day": day})
        return {"status": "deleted"}
