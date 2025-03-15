import uuid
from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=True)
    type = Column(String(50), nullable=False)   # "direct", "group"
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    # no relationship fields

class UsersConversation(Base):
    __tablename__ = "users_conversation"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)         # no ForeignKey
    conversation_id = Column(UUID(as_uuid=True), nullable=False) # no ForeignKey
    role_in_convo = Column(String(255), nullable=True)
    joined_at = Column(DateTime(timezone=True), server_default=func.now())

class Message(Base):
    __tablename__ = "messages"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), nullable=False) # no ForeignKey
    user_id = Column(UUID(as_uuid=True), nullable=False)         # no ForeignKey
    content = Column(Text, nullable=False)
    type = Column(String(50), nullable=False)
    sent_at = Column(DateTime(timezone=True), server_default=func.now())