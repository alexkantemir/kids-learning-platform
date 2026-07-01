from pydantic import BaseModel, field_validator
import re


class LoginRequest(BaseModel):
    username: str
    password: str

    @field_validator("username")
    @classmethod
    def clean_username(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r'^[a-zA-Z0-9_]{3,64}$', v):
            raise ValueError("Username must be 3-64 alphanumeric characters or underscores")
        return v


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    user_id: int
    child_id: int | None = None


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "parent"

    @field_validator("username")
    @classmethod
    def clean_username(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r'^[a-zA-Z0-9_]{3,64}$', v):
            raise ValueError("Username must be 3-64 alphanumeric characters or underscores")
        return v

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        if len(v) < 6:
            raise ValueError("Password must be at least 6 characters")
        return v
