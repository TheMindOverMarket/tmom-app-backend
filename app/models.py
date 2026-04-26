from sqlmodel import SQLModel, Field, Column, DateTime, JSON, Text, text
from datetime import datetime, timezone
from typing import Optional, Any, Dict, List
import uuid
from sqlalchemy import func, Enum as SAEnum, ForeignKey
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
    INITIALIZING = "INITIALIZING"
    INCOMPLETE = "INCOMPLETE"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"

class SessionEventType(str, Enum):
    ADHERENCE = "ADHERENCE"
    DEVIATION = "DEVIATION"
    NOTIFICATION = "NOTIFICATION"
    TRADING = "TRADING"
    SYSTEM = "SYSTEM"

class UserRole(str, Enum):
    TRADER = "TRADER"
    MANAGER = "MANAGER"

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
    first_name: Optional[str] = Field(default=None)
    last_name: Optional[str] = Field(default=None)
    hashed_password: Optional[str] = Field(default=None)
    role: UserRole = Field(
        sa_column=Column(
            SAEnum(UserRole, name="user_role_enum"),
            server_default=UserRole.TRADER.value,
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
        sa_column=Column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    )
    name: str = Field(nullable=False)
    # Temporary compatibility:
    # keep these optional at the ORM layer so older rows can still be read
    # while symbol/market migrations finish rolling out and backfills settle.
    # Dirty implementation note: hydration in the playbook router still normalizes
    # older rows on read until proper backfills/auth-driven ownership are in place.
    symbol: Optional[str] = Field(index=True, nullable=True, default=None)
    market: Optional[str] = Field(index=True, nullable=True, default=None)
    original_nl_input: str = Field(
        sa_column=Column(Text, nullable=False)
    )
    context: Optional[Dict[str, Any]] = Field(
        default=None, 
        sa_column=Column(JSON)
    )
    chat_history: Optional[List[Dict[str, Any]]] = Field(
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
        sa_column=Column(ForeignKey("playbooks.id", ondelete="CASCADE"), index=True, nullable=False)
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
        sa_column=Column(ForeignKey("rules.id", ondelete="CASCADE"), index=True, nullable=False)
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
        sa_column=Column(ForeignKey("rules.id", ondelete="CASCADE"), index=True, nullable=False)
    )
    parent_condition_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("conditions.id", ondelete="CASCADE"), index=True, nullable=False)
    )
    child_condition_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("conditions.id", ondelete="CASCADE"), index=True, nullable=False)
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
        sa_column=Column(ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    )
    playbook_id: uuid.UUID = Field(
        sa_column=Column(ForeignKey("playbooks.id", ondelete="CASCADE"), index=True, nullable=False)
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
    is_audit_ready: bool = Field(default=False, nullable=False)

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
        sa_column=Column(ForeignKey("sessions.id", ondelete="CASCADE"), index=True, nullable=False)
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
