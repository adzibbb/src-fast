from pydantic import BaseModel, EmailStr, field_validator, ValidationInfo, ConfigDict
from datetime import datetime
from typing import Optional
import uuid
from app.core.validators import validate_password, validate_username


class UserBase(BaseModel):
    username: str
    display_name: str


class UserCreate(UserBase):
    email: EmailStr
    password: str

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: str, info: ValidationInfo) -> str:
        errors = validate_password(v)
        if errors:
            error_message = ', '.join(errors)
            raise ValueError(error_message)
        return v

    @field_validator('username')
    @classmethod
    def validate_username(cls, v: str, info: ValidationInfo) -> str:
        errors = validate_username(v)
        if errors:
            error_message = ', '.join(errors)
            raise ValueError(error_message)
        return v


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    display_name: Optional[str] = None
    password: Optional[str] = None

    @field_validator('password')
    @classmethod
    def validate_password(cls, v: Optional[str], info: ValidationInfo) -> Optional[str]:
        if v is None:
            return v

        errors = validate_password(v)
        if errors:
            error_message = ', '.join(errors)
            raise ValueError(error_message)
        return v


class UserInDB(UserBase):
    id: uuid.UUID
    email: EmailStr
    total_points: int
    created_at: datetime
    last_login_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True, extra='forbid')


class User(UserInDB):
    model_config = ConfigDict(from_attributes=True, extra='forbid')


class LoginRequest(BaseModel):
    username: str
    password: str
    remember_me: bool = False


class AuthResponse(BaseModel):
    success: bool
    user_id: Optional[uuid.UUID] = None
    username: Optional[str] = None
    display_name: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = None
    errors: Optional[list[str]] = None


class UserLeaderboard(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str
    total_points: int
    post_count: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
