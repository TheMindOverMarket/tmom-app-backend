from sqlmodel import SQLModel, Field, Column, DateTime, JSON, Text, text
from datetime import datetime, timezone
from typing import Optional, Any, Dict
import uuid
from sqlalchemy import func, Enum as SAEnum
from enum import Enum

class LogicalOperator(str, Enum):
    AND = "AND"
    OR = "OR"

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
            server_default=func.now(),
            nullable=False
        )
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
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
    is_active: bool = Field(default=True, nullable=False)
    
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False
        )
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
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
    is_active: bool = Field(default=True, nullable=False)
    
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False
        )
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
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
            server_default=func.now(),
            nullable=False
        )
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
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
            server_default=func.now(),
            nullable=False
        )
    )
