from pydantic import BaseModel, EmailStr
from typing import Optional

# Create User
class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    role: str = "viewer"

# User Response
class UserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: str

    class Config:
        from_attributes = True

# Login
class UserLogin(BaseModel):
    email: EmailStr
    password: str

# JWT Token
class Token(BaseModel):
    access_token: str
    token_type: str

# Token Payload
class TokenData(BaseModel):
    email: Optional[str] = None