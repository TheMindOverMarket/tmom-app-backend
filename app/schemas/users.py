import uuid
from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    id: Optional[uuid.UUID] = None
    email: EmailStr

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
