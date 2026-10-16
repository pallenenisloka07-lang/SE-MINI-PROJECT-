
import os
from pathlib import Path

from sqlalchemy import (
    Boolean,
    Column,
    Integer,
    String,
    create_engine,
)
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{Path('users.db').resolve().as_posix()}",
)

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
    if DATABASE_URL.startswith("sqlite")
    else {},
)

SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(254), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="User")
    is_active = Column(Boolean, nullable=False, default=True)


def init_db():
    Base.metadata.create_all(bind=engine)


def create_user(username, email, password_hash):
    with SessionLocal() as db:
        user = User(
            username=username,
            email=email,
            password_hash=password_hash,
            role="User",
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return {
            "id": user.id,
            "username": user.username,
            "role": user.role,
        }


def find_user_by_username(username):
    with SessionLocal() as db:
        return db.query(User).filter(
            User.username == username
        ).first()


def find_user_by_email(email):
    with SessionLocal() as db:
        return db.query(User).filter(
            User.email == email
        ).first()
