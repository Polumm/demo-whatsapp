import uuid
from sqlalchemy import Column, String, DateTime, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from dependencies import Base

class Presence(Base):
    __tablename__ = "presence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    node_id = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)  # 'online','offline'
    last_online = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    device_id = Column(String(255), nullable=False)  # New column for device identification
    
    __table_args__ = (
        UniqueConstraint('user_id', 'device_id', name='uq_user_device'),  # Optional: Ensure one presence per device per user
    )