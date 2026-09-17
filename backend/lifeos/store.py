import hashlib
import json
import time
import uuid
import threading
from sqlalchemy import create_engine, String, Text, Float, Integer, select, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy import text


def uid():
    return uuid.uuid4().hex


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def requires_reconciliation(event):
    return event.get("status") in {"executing", "verifying", "running"} or any(
        action.get("status") in {"executing", "uncertain"}
        or action.get("compensation_status") in {"executing", "uncertain"}
        for action in event.get("actions", [])
    )


class Base(DeclarativeBase):
    pass


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(100), primary_key=True)
    owner: Mapped[str] = mapped_column(String(100), index=True)
    kind: Mapped[str] = mapped_column(String(40), index=True)
    data: Mapped[str] = mapped_column(Text)
    created: Mapped[float] = mapped_column(Float, default=time.time)
    revision: Mapped[int] = mapped_column(Integer, default=1)


class Database:
    def __init__(self, url):
        if url.startswith("sqlite:///") and ":memory:" not in url:
            from pathlib import Path

            Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
        kwargs = {"connect_args": {"check_same_thread": False}} if url.startswith("sqlite") else {}
        if url in ["sqlite://", "sqlite:///:memory:"]:
            kwargs["poolclass"] = StaticPool
        self.engine = create_engine(url, **kwargs)
        self.migrate()
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.audit_lock = threading.RLock()

    def migrate(self):
        """Apply schema revisions once; refuse databases from newer code."""
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS schema_revision (id INTEGER PRIMARY KEY, version INTEGER NOT NULL)"
                )
            )
            version = connection.execute(text("SELECT version FROM schema_revision WHERE id=1")).scalar()
            if version is not None and version > 2:
                raise RuntimeError("Database schema is newer than this application")
            if version is None:
                Base.metadata.create_all(connection)
                connection.execute(text("INSERT INTO schema_revision (id,version) VALUES (1,1)"))
            if version is None or version < 2:
                connection.execute(text(
                    "CREATE INDEX IF NOT EXISTS ix_documents_owner_kind_created "
                    "ON documents (owner, kind, created)"
                ))
                connection.execute(text("UPDATE schema_revision SET version=2 WHERE id=1"))

    def prune_events(self, owner, days):
        with self.sessions.begin() as session:
            rows = session.scalars(
                select(Document).where(
                    Document.owner == owner,
                    Document.kind == "event",
                    Document.created < time.time() - days * 86400,
                )
            )
            for row in rows:
                if not requires_reconciliation(json.loads(row.data)):
                    session.delete(row)

    def prune_sessions(self):
        with self.sessions.begin() as session:
            for row in session.scalars(
                select(Document).where(Document.owner == "system", Document.kind == "session")
            ):
                if json.loads(row.data).get("expires", 0) < time.time():
                    session.delete(row)

    def get(self, owner, kind, id):
        with self.sessions() as session:
            row = session.get(Document, id)
            return json.loads(row.data) if row and row.owner == owner and row.kind == kind else None

    def list(self, owner, kind):
        with self.sessions() as session:
            rows = session.scalars(
                select(Document)
                .where(Document.owner == owner, Document.kind == kind)
                .order_by(Document.created, Document.id)
            )
            return [json.loads(r.data) for r in rows]

    def latest(self, owner, kind):
        with self.sessions() as session:
            row = session.scalar(
                select(Document)
                .where(Document.owner == owner, Document.kind == kind)
                .order_by(Document.created.desc(), Document.id.desc())
                .limit(1)
            )
            return json.loads(row.data) if row else None

    def list_page(self, owner, kind, offset, limit):
        with self.sessions() as session:
            predicate = (Document.owner == owner, Document.kind == kind)
            total = session.scalar(select(func.count()).select_from(Document).where(*predicate)) or 0
            rows = session.scalars(
                select(Document).where(*predicate)
                .order_by(Document.created.desc(), Document.id.desc())
                .offset(offset).limit(limit)
            ).all()
            return [json.loads(row.data) for row in rows], total

    def list_since(self, owner, kind, timestamp):
        with self.sessions() as session:
            rows = session.scalars(
                select(Document).where(
                    Document.owner == owner, Document.kind == kind, Document.created >= timestamp,
                ).order_by(Document.created)
            )
            return [json.loads(row.data) for row in rows]

    def put(self, owner, kind, id, data):
        with self.sessions.begin() as session:
            row = session.get(Document, id)
            if row:
                if row.owner != owner or row.kind != kind:
                    raise ValueError("Ownership mismatch")
                row.data = json.dumps(data)
                row.revision += 1
            else:
                session.add(Document(id=id, owner=owner, kind=kind, data=json.dumps(data)))

    def delete_kind(self, owner, kind):
        from sqlalchemy import delete

        with self.sessions.begin() as session:
            session.execute(delete(Document).where(Document.owner == owner, Document.kind == kind))

    def delete(self, owner, kind, id):
        from sqlalchemy import delete

        with self.sessions.begin() as session:
            session.execute(
                delete(Document).where(Document.owner == owner, Document.kind == kind, Document.id == id)
            )

    def consume(self, owner, kind, id):
        """Atomically remove and return a one-use document."""
        from sqlalchemy import delete

        with self.sessions.begin() as session:
            raw = session.execute(
                delete(Document)
                .where(Document.owner == owner, Document.kind == kind, Document.id == id)
                .returning(Document.data)
            ).scalar_one_or_none()
            return json.loads(raw) if raw is not None else None

    def audit(self, owner, stage, message, event_id=None, details=None):
        with self.audit_lock:
            return self._append_audit(owner, stage, message, event_id, details)

    def _append_audit(self, owner, stage, message, event_id=None, details=None):
        previous = self.latest(owner, "audit")
        entry = {
            "id": uid(),
            "timestamp": time.time(),
            "stage": stage,
            "message": message,
            "event_id": event_id,
            "details": details or {},
            "previous_hash": previous["hash"] if previous else "0" * 64,
        }
        entry["hash"] = digest(entry)
        self.put(owner, "audit", entry["id"], entry)
        return entry
