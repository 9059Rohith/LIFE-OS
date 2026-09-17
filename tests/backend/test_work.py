"""A fresh live workspace persists linked records without sample content."""

from cryptography.fernet import Fernet
from fastapi import Response
from fastapi.testclient import TestClient

from lifeos.config import Settings
from lifeos.main import create_app


def test_fresh_live_workflow_and_isolation(tmp_path):
    settings = Settings(
        mode="live", environment="test", auth_password="a-strong-test-password-only",
        encryption_key=Fernet.generate_key().decode(),
        database_url=f"sqlite:///{tmp_path}/work.db",
    )
    with TestClient(create_app(settings)) as first:
        from datetime import datetime
        from zoneinfo import ZoneInfo
        day = datetime.now(ZoneInfo("Asia/Kolkata")).date().isoformat()
        session = first.post("/api/auth/login", json={"password": settings.auth_password}).json()
        first.headers["X-CSRF-Token"] = session["csrf_token"]
        assert first.get("/api/work/summary").json()["tasks"] == 0
        assert first.get("/api/work/projects").json()["items"] == []

        project = first.post("/api/work/projects", json={"title": "Release"}).json()
        goal = first.post("/api/work/goals", json={"title": "Ship", "project_id": project["id"], "target_date": day}).json()
        task = first.post("/api/work/tasks", json={"title": "Verify", "goal_id": goal["id"], "due_date": day}).json()
        habit = first.post("/api/work/habits", json={"title": "Review", "goal_id": goal["id"]}).json()
        note = first.post("/api/work/notes", json={"title": "Evidence", "body": "Read-back complete", "task_id": task["id"]}).json()
        assert all(item["id"] for item in (project, goal, task, habit, note))
        dashboard = first.get("/api/work/dashboard?collection=tasks").json()
        assert dashboard["page"]["items"][0]["id"] == task["id"]
        assert dashboard["links"]["projects"][0]["id"] == project["id"]
        assert dashboard["summary"]["tasks"] == 1
        notices = first.get("/api/work/notifications").json()
        assert {notice["category"] for notice in notices} == {"task_due", "habit_due"}
        task_notice = next(notice for notice in notices if notice["category"] == "task_due")
        assert first.post(f"/api/work/notifications/{task_notice['id']}/dismiss").status_code == 200
        assert all(notice["category"] != "task_due" for notice in first.get("/api/work/notifications").json())
        assert first.delete(f"/api/work/projects/{project['id']}").status_code == 409
        assert first.patch(f"/api/work/tasks/{task['id']}", json={"status": "done"}).json()["completed_at"]
        assert first.get("/api/work/summary").json()["project_progress"][0]["completed"] == 1
        assert {item["kind"] for item in first.get("/api/work/calendar").json()["items"]} == {"task", "goal"}

        assert first.post(f"/api/work/habits/{habit['id']}/checkins", json={"day": day}).status_code == 200
        assert first.get("/api/work/habits").json()["items"][0]["streak"] == 1
        assert first.get("/api/work/notifications").json() == []
        assert first.get("/api/privacy/export").json()["work_notes"][0]["id"] == note["id"]
        assert first.get("/api/work/tasks?offset=1&limit=1").json()["items"] == []
        assert first.post("/api/work/tasks", json={"title": "Wrong", "unknown": True}).status_code == 422
        assert first.post("/api/work/tasks", json={"title": "   "}).status_code == 422
        assert first.post("/api/work/tasks", json={"title": "Wrong", "goal_id": "missing"}).status_code == 404

        with TestClient(create_app(settings)) as second:
            session_2 = second.post("/api/auth/login", json={"password": settings.auth_password}).json()
            second.headers["X-CSRF-Token"] = session_2["csrf_token"]
            assert second.get("/api/work/summary").json()["tasks"] == 1
            assert second.get("/api/work/tasks").json()["items"][0]["id"] == task["id"]
            isolated_response = Response()
            isolated = second.app.state.security.create(isolated_response, "another-owner")
            cookie = isolated_response.headers["set-cookie"].split(";", 1)[0].split("=", 1)[1]
            second.cookies.set("lifeos_session", cookie)
            second.headers["X-CSRF-Token"] = isolated["csrf"]
            assert second.get("/api/work/summary").json()["tasks"] == 0
            assert second.patch(f"/api/work/tasks/{task['id']}", json={"status": "done"}).status_code == 404

        assert first.get("/api/work/tasks").json()["items"][0]["status"] == "done"
        assert first.delete(f"/api/work/notes/{note['id']}").status_code == 200
        assert first.delete(f"/api/work/tasks/{task['id']}").status_code == 200
        assert first.get("/api/work/summary").json()["tasks"] == 0


def test_dashboard_link_options_include_older_records_after_one_hundred(tmp_path):
    settings = Settings(
        mode="live", environment="test", auth_password="a-strong-test-password-only",
        encryption_key=Fernet.generate_key().decode(),
        database_url=f"sqlite:///{tmp_path}/many-work-items.db", rate_limit=500,
    )
    with TestClient(create_app(settings)) as client:
        session = client.post("/api/auth/login", json={"password": settings.auth_password}).json()
        client.headers["X-CSRF-Token"] = session["csrf_token"]
        oldest = client.post("/api/work/projects", json={"title": "Oldest project"}).json()
        for number in range(101):
            assert client.post("/api/work/projects", json={"title": f"Project {number}"}).status_code == 200
        dashboard = client.get("/api/work/dashboard?collection=tasks").json()
        assert dashboard["summary"]["projects"] == 102
        assert len(dashboard["links"]["projects"]) == 102
        assert {"id": oldest["id"], "title": "Oldest project"} in dashboard["links"]["projects"]
        assert client.get("/api/audit/verify").json()["valid"] is True
