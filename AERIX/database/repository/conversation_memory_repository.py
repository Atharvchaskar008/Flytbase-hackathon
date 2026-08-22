import uuid
from datetime import datetime
from sqlalchemy.orm import Session

from database.models.conversation_memory import ConversationMemory


def _ensure_uuid(value: uuid.UUID | str | None) -> uuid.UUID | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(value)


def save_memory(
    db: Session,
    *,
    conversation_id: str,
    memory_key: str,
    memory_value: str,
    user_id: uuid.UUID | str | None = None,
) -> ConversationMemory:
    memory = ConversationMemory(
        conversation_id=conversation_id,
        memory_key=memory_key,
        memory_value=memory_value,
        user_id=_ensure_uuid(user_id),
    )
    db.add(memory)
    db.flush()
    return memory


def get_memory(db: Session, conversation_id: str, memory_key: str):
    return (
        db.query(ConversationMemory)
        .filter(
            ConversationMemory.conversation_id == conversation_id,
            ConversationMemory.memory_key == memory_key,
        )
        .order_by(ConversationMemory.created_at.desc())
        .first()
    )


def list_recent_memory(db: Session, conversation_id: str, limit: int = 10):
    return (
        db.query(ConversationMemory)
        .filter(ConversationMemory.conversation_id == conversation_id)
        .order_by(ConversationMemory.created_at.desc())
        .limit(limit)
        .all()
    )
