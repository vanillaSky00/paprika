from typing import List
from ..api.schemas import MemoryDTO, CreateMemoryDTO
from .base import BaseMemoryStore
from .models import Memory 
from .vector_store import embed_text

class PostgresMemoryStore(BaseMemoryStore):
    def __init__(self, session_factory):
        self._session_factory = session_factory

    def save(self, memory: CreateMemoryDTO) -> None:
        with self._session_factory() as db:
            emb = embed_text(memory.content)
            
            # Map Pydantic Input -> SQLAlchemy Table
            db_mem = Memory(
                in_game_day=memory.day,
                time_slot=memory.time,
                mode=memory.mode,
                location=memory.location,
                memory_type=memory.memory_type,
                content=memory.content,
                emotion_tags=memory.emotion_tags,
                importance=memory.importance,
                embedding=emb
            )
            db.add(db_mem)
            db.commit()

    def fetch_recent(self, *, day: int, limit: int = 20) -> List[MemoryDTO]:
        with self._session_factory() as db:
            rows = (
                db.query(Memory)
                  .filter(Memory.in_game_day <= day)
                  .order_by(Memory.in_game_day.desc(), Memory.time_slot.desc())
                  .limit(limit)
                  .all()
            )
            # MAGIC: Convert SQL Object -> Pydantic DTO safely
            return [MemoryDTO.model_validate(row) for row in rows]

    def fetch_similar(self, *, query: str, limit: int = 10) -> List[MemoryDTO]:
        with self._session_factory() as db:
            q_emb = embed_text(query)
            rows = (
                db.query(Memory)
                  .order_by(Memory.embedding.l2_distance(q_emb))
                  .limit(limit)
                  .all()
            )
            return [MemoryDTO.model_validate(row) for row in rows]