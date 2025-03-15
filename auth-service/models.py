import uuid
from sqlalchemy import Column, String, TIMESTAMP, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, unique=True
    )
    name = Column(String(255), nullable=False, unique=True)
    role = Column(String(255), nullable=False)  # e.g., "user", "admin"
    password = Column(String(255), nullable=False)  # Store hashed password
    created_at = Column(
        TIMESTAMP, nullable=False, server_default=func.now()
    )  # Auto-set timestamp
