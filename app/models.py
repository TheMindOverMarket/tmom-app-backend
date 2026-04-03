from sqlmodel import SQLModel, Field, Column, DateTime, JSON, Text, text
from datetime import datetime, timezone
from typing import Optional, Any, Dict
import uuid
from sqlalchemy import func, Enum as SAEnum
from enum import Enum

class LogicalOperator(str, Enum):
    AND = "AND"
    OR = "OR"

class SessionStatus(str, Enum):
    STARTED = "STARTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class GenerationStatus(str, Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class SessionEventType(str, Enum):
    ADHERENCE = "ADHERENCE"
    DEVIATION = "DEVIATION"
    NOTIFICATION = "NOTIFICATION"
    TRADING = "TRADING"
    SYSTEM = "SYSTEM"

class User(SQLModel, table=True):
    __tablename__ = "users"
    
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False
    )
    email: str = Field(
        unique=True,
        index=True,
        nullable=False
    )
    
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False
        )
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            onupdate=text("CURRENT_TIMESTAMP"),
            nullable=False
        )
    )

class Playbook(SQLModel, table=True):
    __tablename__ = "playbooks"
    
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False
    )
    user_id: uuid.UUID = Field(
        foreign_key="users.id",
        index=True,
        nullable=False
    )
    name: str = Field(nullable=False)
    symbol: str = Field(index=True, nullable=False, default="BTC/USD")
    market: str = Field(index=True, nullable=False, default="BTC/USD")
    original_nl_input: str = Field(
        sa_column=Column(Text, nullable=False)
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None, 
        sa_column=Column(JSON)
    )
    is_active: bool = Field(default=True, nullable=False)
    generation_status: GenerationStatus = Field(
        sa_column=Column(
            SAEnum(GenerationStatus, name="generation_status_enum"),
            server_default=GenerationStatus.COMPLETED.value,
            nullable=False
        )
    )
    failure_reason: Optional[str] = Field(
        default=None,
        sa_column=Column(Text, nullable=True)
    )
    
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False
        )
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            onupdate=text("CURRENT_TIMESTAMP"),
            nullable=False
        )
    )

class Rule(SQLModel, table=True):
    __tablename__ = "rules"
    
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False
    )
    playbook_id: uuid.UUID = Field(
        foreign_key="playbooks.id",
        index=True,
        nullable=False
    )
    name: str = Field(nullable=False)
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    category: Optional[str] = Field(default="logic", nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False
        )
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            onupdate=text("CURRENT_TIMESTAMP"),
            nullable=False
        )
    )

class Condition(SQLModel, table=True):
    __tablename__ = "conditions"
    
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False
    )
    rule_id: uuid.UUID = Field(
        foreign_key="rules.id",
        index=True,
        nullable=False
    )
    metric: str = Field(nullable=False)
    comparator: str = Field(nullable=False)
    value: str = Field(nullable=False)
    is_active: bool = Field(default=True, nullable=False)
    
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False
        )
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            onupdate=text("CURRENT_TIMESTAMP"),
            nullable=False
        )
    )

class ConditionEdge(SQLModel, table=True):
    __tablename__ = "condition_edges"
    
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False
    )
    rule_id: uuid.UUID = Field(
        foreign_key="rules.id",
        index=True,
        nullable=False
    )
    parent_condition_id: uuid.UUID = Field(
        foreign_key="conditions.id",
        index=True,
        nullable=False
    )
    child_condition_id: uuid.UUID = Field(
        foreign_key="conditions.id",
        index=True,
        nullable=False
    )
    logical_operator: LogicalOperator = Field(
        sa_column=Column(
            SAEnum(LogicalOperator, name="logical_operator_enum"),
            nullable=False
        )
    )
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False
        )
    )

class Session(SQLModel, table=True):
    __tablename__ = "sessions"
    
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False
    )
    user_id: uuid.UUID = Field(
        foreign_key="users.id",
        index=True,
        nullable=False
    )
    playbook_id: uuid.UUID = Field(
        foreign_key="playbooks.id",
        index=True,
        nullable=False
    )
    start_time: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False
        )
    )
    end_time: Optional[datetime] = Field(
        sa_column=Column(
            DateTime(timezone=True),
            nullable=True
        )
    )
    status: SessionStatus = Field(
        sa_column=Column(
            SAEnum(SessionStatus, name="session_status_enum"),
            server_default=SessionStatus.STARTED.value,
            nullable=False
        )
    )
    session_metadata: Optional[Dict[str, Any]] = Field(
        default=None, 
        sa_column=Column(JSON)
    )

    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False
        )
    )

class SessionEvent(SQLModel, table=True):
    __tablename__ = "session_events"
    
    id: uuid.UUID = Field(
        default_factory=uuid.uuid4,
        primary_key=True,
        index=True,
        nullable=False
    )
    session_id: uuid.UUID = Field(
        foreign_key="sessions.id",
        index=True,
        nullable=False
    )
    type: SessionEventType = Field(
        sa_column=Column(
            SAEnum(SessionEventType, name="session_event_type_enum"),
            nullable=False
        )
    )
    timestamp: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False
        )
    )
    tick: Optional[int] = Field(nullable=True)
    
    event_data: Dict[str, Any] = Field(
        sa_column=Column(JSON, nullable=False)
    )
    event_metadata: Optional[Dict[str, Any]] = Field(
        default=None, 
        sa_column=Column(JSON)
    )

    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=text("CURRENT_TIMESTAMP"),
            nullable=False
        )
    )
