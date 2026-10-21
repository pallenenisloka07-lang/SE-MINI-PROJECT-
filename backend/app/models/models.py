
from datetime import datetime, timezone

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, ForeignKey,
    Float, Boolean, CheckConstraint
)
from sqlalchemy.orm import relationship

from backend.app.database.connection import Base


def utc_now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="user")

    __table_args__ = (
        CheckConstraint("role IN ('user', 'admin')", name="check_user_role"),
    )

    documents = relationship("Document", back_populates="owner")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=False)

    documents = relationship("Document", back_populates="category")


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)

    title = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_type = Column(String(20), nullable=False)
    file_size = Column(Integer, nullable=False)
    storage_path = Column(String(500), nullable=False, unique=True)

    status = Column(String(20), nullable=False, default="Uploaded")
    upload_date = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    extracted_text = Column(Text, default="")
    category_score = Column(Float, nullable=True)
    category_source = Column(String(20), nullable=False, default="auto")
    failure_reason = Column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('Uploaded', 'Processing', 'Processed', 'Failed')",
            name="check_document_status",
        ),
        CheckConstraint(
            "category_source IN ('auto', 'manual')",
            name="check_category_source",
        ),
    )

    owner = relationship("User", back_populates="documents")
    category = relationship("Category", back_populates="documents")
    keywords = relationship(
        "DocumentKeyword", back_populates="document",
        cascade="all, delete-orphan"
    )
    topics = relationship(
        "DocumentTopic", back_populates="document",
        cascade="all, delete-orphan"
    )


class DocumentKeyword(Base):
    __tablename__ = "document_keywords"

    id = Column(Integer, primary_key=True)
    document_id = Column(
        Integer, ForeignKey("documents.id"), nullable=False, index=True
    )
    phrase = Column(String(255), nullable=False)
    score = Column(Float, nullable=False)
    rank = Column(Integer, nullable=False)

    document = relationship("Document", back_populates="keywords")


class DocumentTopic(Base):
    __tablename__ = "document_topics"

    id = Column(Integer, primary_key=True)
    document_id = Column(
        Integer, ForeignKey("documents.id"), nullable=False, index=True
    )
    label = Column(String(255), nullable=False)
    rank = Column(Integer, nullable=False)

    document = relationship("Document", back_populates="topics")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)
    details = Column(Text, default="")
    timestamp = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id = Column(Integer, primary_key=True)
    token_id = Column(String(255), unique=True, nullable=False, index=True)
    revoked_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)

