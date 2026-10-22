from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    String,
    Text,
)

from src.repositories.user_repository import (
    Base,
    SessionLocal,
    engine,
)
from src.repositories.document_repository import Document


DEFAULT_CATEGORIES = {
    "Technology": (
        "Software, computers, programming, digital systems, "
        "artificial intelligence, data platforms and cybersecurity."
    ),
    "Business and Finance": (
        "Business strategy, companies, accounting, banking, "
        "investments, budgets, financial markets and commerce."
    ),
    "Education": (
        "Schools, universities, students, teaching, academic "
        "courses, learning methods, assessments and curriculum."
    ),
    "Health and Medicine": (
        "Healthcare, diseases, medical research, patients, "
        "clinical practice, diagnosis, treatment and medicine."
    ),
    "Law and Government": (
        "Legislation, courts, legal systems, public policy, "
        "government institutions, regulations and civic affairs."
    ),
    "Science and Research": (
        "Scientific methods, experiments, research findings, "
        "physics, chemistry, biology and academic investigations."
    ),
}


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    description = Column(String(500), nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
    )


class AuditEvent(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    username = Column(String(100), nullable=True)
    action = Column(String(100), nullable=False, index=True)
    details = Column(Text, nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )


def init_admin_tables():
    """Create administration tables and seed defaults on first setup."""
    Base.metadata.create_all(bind=engine)

    with SessionLocal() as db:
        if db.query(Category).count() == 0:
            db.add_all(
                [
                    Category(name=name, description=description)
                    for name, description in DEFAULT_CATEGORIES.items()
                ]
            )
            db.commit()


def list_categories():
    with SessionLocal() as db:
        categories = (
            db.query(Category)
            .order_by(Category.name.asc())
            .all()
        )

        return [
            {
                "id": item.id,
                "name": item.name,
                "description": item.description,
            }
            for item in categories
        ]


def create_category(name, description):
    name = name.strip()
    description = description.strip()

    if not name or len(name) > 100:
        raise ValueError("Category name must contain 1–100 characters")

    if name.casefold() == "uncategorized":
        raise ValueError(
            "Uncategorized is reserved for the system"
        )

    if not description or len(description) > 500:
        raise ValueError(
            "Description must contain 1–500 characters"
        )

    with SessionLocal() as db:
        existing = db.query(Category).all()

        if any(item.name.casefold() == name.casefold()
               for item in existing):
            raise ValueError("A category with this name already exists")

        category = Category(
            name=name,
            description=description,
        )

        db.add(category)
        db.commit()
        db.refresh(category)

        return {
            "id": category.id,
            "name": category.name,
            "description": category.description,
        }


def delete_category(category_id):
    """Delete a category and reset its documents to Uncategorized."""
    with SessionLocal() as db:
        category = db.get(Category, category_id)

        if category is None:
            return None

        category_data = {
            "id": category.id,
            "name": category.name,
            "description": category.description,
        }

        documents = (
            db.query(Document)
            .filter(Document.category == category.name)
            .all()
        )

        for document in documents:
            document.category = "Uncategorized"
            document.category_confidence = None
            document.category_is_manual = False

        affected_count = len(documents)

        db.delete(category)
        db.commit()

        return {
            "category": category_data,
            "documents_reset": affected_count,
        }


def record_audit_event(
    user_id,
    username,
    action,
    details="",
):
    """Record an event without storing passwords, tokens or document text."""
    with SessionLocal() as db:
        event = AuditEvent(
            user_id=user_id,
            username=(username or "")[:100] or None,
            action=action[:100],
            details=(details or "")[:1000],
        )

        db.add(event)
        db.commit()
        db.refresh(event)

        return {
            "id": event.id,
            "user_id": event.user_id,
            "username": event.username,
            "action": event.action,
            "details": event.details,
            "created_at": event.created_at,
        }


def list_audit_events(offset=0, limit=10):
    with SessionLocal() as db:
        query = db.query(AuditEvent)
        total = query.count()

        events = (
            query.order_by(
                AuditEvent.created_at.desc(),
                AuditEvent.id.desc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )

        items = [
            {
                "id": event.id,
                "user_id": event.user_id,
                "username": event.username,
                "action": event.action,
                "details": event.details,
                "created_at": event.created_at.isoformat(),
            }
            for event in events
        ]

        return {
            "items": items,
            "total": total,
            "offset": offset,
            "limit": limit,
        }