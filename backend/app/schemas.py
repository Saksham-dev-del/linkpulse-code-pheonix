from pydantic import BaseModel, HttpUrl, Field, field_validator
from typing import Optional
from datetime import datetime

class LinkCreate(BaseModel):
    destination_url: str
    alias: Optional[str] = Field(default=None, min_length=3, max_length=32)
    campaign: str = Field(default="General", max_length=120)
    tags: list[str] = []
    expires_at: Optional[datetime] = None
    click_cap: Optional[int] = Field(default=None, ge=1)
    password: Optional[str] = Field(default=None, min_length=3, max_length=128)

    @field_validator("destination_url")
    @classmethod
    def valid_destination(cls, value):
        value = value.strip()
        if not value.startswith(("https://", "http://")):
            raise ValueError("Destination URL must start with http:// or https://")
        return value

    @field_validator("alias")
    @classmethod
    def valid_alias(cls, value):
        if value and not value.replace("-", "").replace("_", "").isalnum():
            raise ValueError("Alias may contain letters, numbers, hyphens and underscores only")
        return value

class StatusUpdate(BaseModel):
    status: str
    @field_validator("status")
    @classmethod
    def valid_status(cls, value):
        if value not in {"active", "disabled"}:
            raise ValueError("Status must be active or disabled")
        return value


class LinkUpdate(BaseModel):
    destination_url: Optional[str] = None
    campaign: Optional[str] = Field(default=None, max_length=120)
    tags: Optional[list[str]] = None
    expires_at: Optional[datetime] = None
    click_cap: Optional[int] = Field(default=None, ge=1)
    password: Optional[str] = Field(default=None, min_length=3, max_length=128)

    @field_validator("destination_url")
    @classmethod
    def valid_update_destination(cls, value):
        if value is None:
            return value
        value = value.strip()
        if not value.startswith(("https://", "http://")):
            raise ValueError("Destination URL must start with http:// or https://")
        return value

class BulkLinkCreate(BaseModel):
    links: list[LinkCreate]
