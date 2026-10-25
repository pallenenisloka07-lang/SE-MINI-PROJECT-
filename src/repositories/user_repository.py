import os
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import declarative_base, sessionmaker


# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./users.db")

engine = create_engine(
    DATABASE_URL,
    connect_args=(
        {"check_same_thread": False}
        if DATABASE_URL.startswith("sqlite")
        else {}
    ),
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


# User table
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(254), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="User")
    is_active = Column(Boolean, nullable=False, default=True)


# Revoked access-token table for FR-003
class RevokedToken(Base):
    __tablename__ = "revoked_tokens"

    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String(64), unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)


def init_db():
    """Create database tables if they do not already exist."""
    Base.metadata.create_all(bind=engine)


def create_user(username, email, password_hash):
    """Create a user and return safe user details."""
    with SessionLocal() as db:
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            role="User",
        )

        try:
            db.add(user)
            db.commit()
            db.refresh(user)

            return {
                "id": user.id,
                "username": user.username,
                "role": user.role,
            }

        except IntegrityError:
            db.rollback()
            raise


def find_user_by_username(username):
    """Find a user by username."""
    with SessionLocal() as db:
        return (
            db.query(User)
            .filter(User.username == username)
            .first()
        )


def find_user_by_email(email):
    """Find a user by email address."""
    with SessionLocal() as db:
        return (
            db.query(User)
            .filter(User.email == email)
            .first()
        )


def revoke_token(jti, expires_at):
    """Persist a token identifier so it cannot be reused after logout."""
    with SessionLocal() as db:
        existing = (
            db.query(RevokedToken)
            .filter(RevokedToken.jti == jti)
            .first()
        )

        if existing is None:
            db.add(
                RevokedToken(
                    jti=jti,
                    expires_at=expires_at,
                )
            )
            db.commit()


def is_token_revoked(jti):
    """Return True if a token identifier has been revoked."""
    with SessionLocal() as db:
        return (
            db.query(RevokedToken.id)
            .filter(RevokedToken.jti == jti)
            .first()
            is not None
        )