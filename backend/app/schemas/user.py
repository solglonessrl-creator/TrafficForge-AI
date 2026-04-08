from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: str
    is_active: bool = True
    subscription_plan: str = "free" # "free", "pro", "enterprise"
    stripe_customer_id: Optional[str] = None
    created_at: datetime

class SubscriptionUpdate(BaseModel):
    plan: str
    status: str # "active", "canceled", "past_due"
