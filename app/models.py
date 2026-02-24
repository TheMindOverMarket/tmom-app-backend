from typing import Optional
from sqlmodel import SQLModel, Field
from datetime import datetime, timezone
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
