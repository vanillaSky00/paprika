from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Actor(Base):
    """
    The central hub for all entities (agents or humans).
    All related data like memories, skills, and messages branch off from here.
    """
    __tablename__ = "actors"
    id = Column(Integer, primary_key=True, index=True)
    kind = Column(String, nullable=True)
    display_name = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # 'cascade="all, delete-orphan"' ensures Python cleans up child data if an Actor is deleted.
    memories = relationship("Memory", back_populates="actor", cascade="all, delete-orphan")
    skills = relationship("Skill", back_populates="actor", cascade="all, delete-orphan")
    
    # Explicit foreign keys are needed here because there are two links to the Message table
    sent_messages = relationship(
        "Message", foreign_keys="Message.from_actor_id", back_populates="sender"
    )
    received_messages = relationship(
        "Message", foreign_keys="Message.to_actor_id", back_populates="recipient"
    )
    

class Memory(Base):
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, index=True)
    
    # 'ondelete="CASCADE"' guarantees DB-level cleanup if an actor is deleted via raw SQL
    actor_id = Column(Integer, ForeignKey("actors.id", ondelete="CASCADE"), nullable=False, index=True)
    actor = relationship("Actor", back_populates="memories")
    
    # Context
    in_game_day = Column(Integer, index=True)
    time_slot = Column(Integer)
    location_id = Column(String)
    mode = Column(String)  
    memory_type = Column(String)  # e.g., "observation", "reflection"

    # Content
    content = Column(Text)
    emotion_tags = Column(JSON, default=list)
    importance = Column(Float, default=0.5)

    embedding = Column(Vector(1536))

    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Skill(Base):
    __tablename__ = "skills"
    
    # Ensures a specific actor cannot learn the exact same skill twice
    __table_args__ = (
        UniqueConstraint("actor_id", "task_name", name="skills_actor_task_unique"),
    )
    
    id = Column(Integer, primary_key=True, index=True)
    actor_id = Column(Integer, ForeignKey("actors.id", ondelete="CASCADE"), nullable=False, index=True)
    actor = relationship("Actor", back_populates="skills")
    
    task_name = Column(String, index=True, nullable=False)   # e.g., "Cook Burger"
    description = Column(Text)                               # Short summary for LLM context
    steps_text = Column(Text)                                # The generic SOP (Step 1, Step 2...)
    code = Column(Text, nullable=True)                       # Future-proof: For Lua/C# scripts
    
    embedding = Column(Vector(1536))                         
    
    success_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    
class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True)
    from_actor_id = Column(Integer, ForeignKey("actors.id", ondelete="CASCADE"), nullable=False, index=True)
    to_actor_id = Column(Integer, ForeignKey("actors.id", ondelete="CASCADE"), nullable=True, index=True)
    
    channel = Column(String, nullable=False, default="global")
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    sender = relationship("Actor", foreign_keys=[from_actor_id], back_populates="sent_messages")
    recipient = relationship("Actor", foreign_keys=[to_actor_id], back_populates="received_messages")