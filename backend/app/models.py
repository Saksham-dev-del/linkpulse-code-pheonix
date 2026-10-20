from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from .db import Base

def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)

class Link(Base):
    __tablename__ = "links"
    id = Column(Integer, primary_key=True, index=True)
    short_code = Column(String(32), unique=True, index=True, nullable=False)
    destination_url = Column(Text, nullable=False)
    campaign = Column(String(120), default="General", index=True)
    tags = Column(String(500), default="")
    password_hash = Column(String(128), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    click_cap = Column(Integer, nullable=True)
    total_clicks = Column(Integer, default=0, nullable=False)
    status = Column(String(20), default="active", nullable=False, index=True)
    created_at = Column(DateTime, default=utcnow, nullable=False)
    clicks = relationship("ClickEvent", back_populates="link", cascade="all, delete-orphan")

class ClickEvent(Base):
    __tablename__ = "click_events"
    id = Column(Integer, primary_key=True, index=True)
    link_id = Column(Integer, ForeignKey("links.id"), nullable=False, index=True)
    clicked_at = Column(DateTime, default=utcnow, nullable=False, index=True)
    referrer = Column(String(500), default="Direct")
    device = Column(String(40), default="Unknown")
    browser = Column(String(80), default="Unknown")
    is_bot = Column(Boolean, default=False)
    visitor_id = Column(String(64), nullable=True)
    link = relationship("Link", back_populates="clicks")
