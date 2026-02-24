from sqlmodel import SQLModel, Field, Column, JSON, Text
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import uuid

class Rule(SQLModel, table=True):
    __tablename__ = "rules"
    
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: str
    playbook_id: str
    rule_text: str = Field(sa_column=Column(Text))
    rule_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    status: str = Field(default="queued")
    
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False
    )
