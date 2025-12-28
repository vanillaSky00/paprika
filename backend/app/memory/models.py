# paprika_agent_backend/memory/models.py
from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, Column, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class Memory(Base):
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, index=True)

    # Context
    in_game_day = Column(Integer, index=True)
    time_slot = Column(Integer)
    location_id = Column(String)
    mode = Column(String)  # "reality" or "dream"
    memory_type = Column(String)  # "observation", "reflection"

    # Content
    content = Column(Text)
    emotion_tags = Column(JSON, default=list)
    importance = Column(Float, default=0.5)

    # Vector (Ensure 1536 matches your embedding model size)
    embedding = Column(Vector(1536))

    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Skill(Base):
    __tablename__ = "skills"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Core identity
    task_name = Column(String, unique=True, index=True)      # e.g., "Cook Burger"
    description = Column(Text)                               # Short summary for fast reading
    steps_text = Column(Text)                                 # The generic SOP (Step 1, Step 2...)
    code = Column(Text, nullable=True)                       # Future-proof: For Lua/C# scripts later
    
    embedding = Column(Vector(1536))                         # Embedding of the description/task_name
    
    # Metadata
    success_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True))