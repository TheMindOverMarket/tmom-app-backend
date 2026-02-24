from sqlmodel import SQLModel, Field, Column, JSON, Text
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import uuid

class Rule(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    rule_nl: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    status: str = Field(default="active")
    
    # You can add more fields as the rule engine evolves:
    # created_by: Optional[str] = None
    # last_triggered: Optional[datetime] = None

class UserActionRun(SQLModel, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: str
    action_type: str  # e.g. "add_rule"
    raw_input_text: str = Field(sa_column=Column(Text))
    rule_output_json: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    status: str = Field(default="pending")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False
    )
