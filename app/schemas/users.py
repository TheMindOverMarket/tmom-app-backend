from pydantic import BaseModel, EmailStr
from typing import Optional

class UserCreate(BaseModel):
    email: EmailStr

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
