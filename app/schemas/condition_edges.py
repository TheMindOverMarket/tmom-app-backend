from pydantic import BaseModel
from typing import Optional
import uuid
from app.models import LogicalOperator

class ConditionEdgeCreate(BaseModel):
    rule_id: uuid.UUID
    parent_condition_id: uuid.UUID
    child_condition_id: uuid.UUID
    logical_operator: LogicalOperator

class ConditionEdgeUpdate(BaseModel):
    logical_operator: Optional[LogicalOperator] = None
