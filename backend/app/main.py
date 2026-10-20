import csv
import io
import os
import re
import secrets
import hashlib
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import qrcode
from fastapi import FastAPI, Depends, HTTPException, Request, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, desc
from dotenv import load_dotenv

from .db import Base, engine, get_db, SessionLocal
from .models import Link, ClickEvent, utcnow
from .schemas import LinkCreate, StatusUpdate, LinkUpdate, BulkLinkCreate

load_dotenv()
Base.metadata.create_all(bind=engine)
app = FastAPI(title="LinkPulse API", version="1.0.0", description="URL shortener, rule engine and analytics")
origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
app.add_middleware(CORSMiddleware, allow_origins=[origin, "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "http://localhost:8000").rstrip("/")

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 150_000).hex()
    return f"{salt}${digest}"

def verify_password(password: str, stored: str) -> bool:
    try:
        salt, digest = stored.split("$", 1)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 150_000).hex()
        return secrets.compare_digest(actual, digest)
    except Exception:
        return False

def serialize_link(link: Link):
    return {
        "id": link.id, "short_code": link.short_code,
        "short_url": f"{PUBLIC_BASE_URL}/{link.short_code}",
        "destination_url": link.destination_url, "campaign": link.campaign,
        "tags": [x for x in (link.tags or "").split(",") if x],
        "expires_at": link.expires_at.isoformat() + "Z" if link.expires_at else None,
        "click_cap": link.click_cap, "total_clicks": link.total_clicks,
        "status": link.status, "created_at": link.created_at.isoformat() + "Z",
        "password_protected": bool(link.password_hash),
        "is_expired": bool(link.expires_at and link.expires_at <= utcnow()),
    }

def make_code(db: Session):
    alphabet = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(12):
        code = "".join(secrets.choice(alphabet) for _ in range(7))
        if not db.query(Link).filter(Link.short_code == code).first():
            return code
    raise HTTPException(500, "Could not generate a unique short code")

def detect_client(user_agent: str):
    ua = (user_agent or "").lower()
    is_bot = any(term in ua for term in ["bot", "spider", "crawler", "preview", "headless"])
    if "mobile" in ua or "android" in ua or "iphone" in ua:
        device = "Mobile"
    elif "ipad" in ua or "tablet" in ua:
        device = "Tablet"
    elif ua:
        device = "Desktop"
    else:
        device = "Unknown"
    if "edg/" in ua: browser = "Edge"
    elif "chrome/" in ua and "chromium" not in ua: browser = "Chrome"
    elif "firefox/" in ua: browser = "Firefox"
    elif "safari/" in ua and "chrome/" not in ua: browser = "Safari"
    else: browser = "Other"
    return is_bot, device, browser

def save_click(link_id: int, referrer: str, user_agent: str, visitor_id: str):
    db = SessionLocal()
    try:
        link = db.query(Link).filter(Link.id == link_id).first()
        if not link:
            return
        is_bot, device, browser = detect_client(user_agent)
        event = ClickEvent(link_id=link_id, referrer=(referrer or "Direct")[:500],
                           device=device, browser=browser, is_bot=is_bot,
                           visitor_id=visitor_id[:64] if visitor_id else None)
        db.add(event)
        if not is_bot:
            link.total_clicks = (link.total_clicks or 0) + 1
        db.commit()
    finally:
        db.close()

@app.get("/api/health")
def health():
    return {"status": "ok", "service": "LinkPulse API", "database": "connected"}

@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)):
    links = db.query(Link).all()
    events = db.query(ClickEvent).all()
    valid_events = [e for e in events if not e.is_bot]
    campaigns = {}
    for link in links:
        campaigns[link.campaign or "General"] = campaigns.get(link.campaign or "General", 0) + link.total_clicks
    top_campaigns = [{"name": k, "clicks": v} for k, v in sorted(campaigns.items(), key=lambda x: x[1], reverse=True)[:5]]
    recent = db.query(ClickEvent).order_by(desc(ClickEvent.clicked_at)).limit(8).all()
    recent_events = [{"id": e.id, "short_code": e.link.short_code if e.link else "—",
                      "clicked_at": e.clicked_at.isoformat() + "Z", "referrer": e.referrer or "Direct",
                      "device": e.device, "browser": e.browser, "is_bot": e.is_bot} for e in recent]
    daily_map = {}
    for event in valid_events:
        day = event.clicked_at.strftime("%b %d")
        daily_map[day] = daily_map.get(day, 0) + 1
    daily = [{"date": k, "clicks": v} for k, v in list(sorted(daily_map.items()))[-7:]]
    return {"total_links": len(links), "total_clicks": sum(l.total_clicks for l in links),
            "unique_visitors": len({e.visitor_id for e in valid_events if e.visitor_id}) or len(valid_events),
            "active_links": sum(1 for l in links if l.status == "active" and not (l.expires_at and l.expires_at <= utcnow())),
            "bot_events": sum(1 for e in events if e.is_bot), "campaigns": top_campaigns,
            "daily_clicks": daily, "recent_events": recent_events,
            "top_links": [serialize_link(x) for x in sorted(links, key=lambda l: l.total_clicks, reverse=True)[:5]]}

@app.get("/api/links")
def list_links(search: str = "", status: str = "all", db: Session = Depends(get_db)):
    query = db.query(Link)
    if search:
        needle = f"%{search}%"
        query = query.filter((Link.short_code.ilike(needle)) | (Link.destination_url.ilike(needle)) | (Link.campaign.ilike(needle)))
    if status in {"active", "disabled"}:
        query = query.filter(Link.status == status)
    return [serialize_link(link) for link in query.order_by(desc(Link.created_at)).all()]

@app.post("/api/links")
def create_link(payload: LinkCreate, db: Session = Depends(get_db)):
    alias = payload.alias.strip() if payload.alias else None
    if alias and db.query(Link).filter(Link.short_code == alias).first():
        raise HTTPException(409, "That custom alias is already taken.")
    code = alias or make_code(db)
    link = Link(short_code=code, destination_url=payload.destination_url,
                campaign=payload.campaign.strip() or "General",
                tags=",".join(dict.fromkeys(t.strip() for t in payload.tags if t.strip()))[:500],
                password_hash=hash_password(payload.password) if payload.password else None,
                expires_at=payload.expires_at.replace(tzinfo=None) if payload.expires_at else None,
                click_cap=payload.click_cap, status="active", total_clicks=0)
    db.add(link)
    db.commit()
    db.refresh(link)
    return serialize_link(link)

@app.get("/api/links/{link_id}")
def get_link(link_id: int, db: Session = Depends(get_db)):
    link = db.query(Link).filter(Link.id == link_id).first()
    if not link: raise HTTPException(404, "Link not found")
    return serialize_link(link)

@app.patch("/api/links/{link_id}/status")
def update_status(link_id: int, payload: StatusUpdate, db: Session = Depends(get_db)):
    link = db.query(Link).filter(Link.id == link_id).first()
    if not link: raise HTTPException(404, "Link not found")
    link.status = payload.status
    db.commit()
    return serialize_link(link)

@app.get("/api/links/{link_id}/analytics")
def link_analytics(link_id: int, db: Session = Depends(get_db)):
    link = db.query(Link).filter(Link.id == link_id).first()
    if not link: raise HTTPException(404, "Link not found")
    events = db.query(ClickEvent).filter(ClickEvent.link_id == link_id).order_by(desc(ClickEvent.clicked_at)).limit(200).all()
    nonbots = [e for e in events if not e.is_bot]
    def group(field):
        counts = {}
        for e in nonbots:
            key = getattr(e, field) or "Direct"
            counts[key] = counts.get(key, 0) + 1
        return [{"name": k, "count": v} for k, v in sorted(counts.items(), key=lambda p: p[1], reverse=True)]
    return {"link": serialize_link(link), "clicks": link.total_clicks,
            "events": [{"id": e.id, "clicked_at": e.clicked_at.isoformat() + "Z", "referrer": e.referrer,
                        "device": e.device, "browser": e.browser, "is_bot": e.is_bot} for e in events],
            "devices": group("device"), "browsers": group("browser"), "referrers": group("referrer")}


@app.patch("/api/links/{link_id}")
def edit_link(link_id: int, payload: LinkUpdate, db: Session = Depends(get_db)):
    """Edit a link's destination and metadata without changing its short code."""
    link = db.query(Link).filter(Link.id == link_id).first()
    if not link:
        raise HTTPException(404, "Link not found")
    data = payload.model_dump(exclude_unset=True)
    if "destination_url" in data and data["destination_url"]:
        link.destination_url = data["destination_url"].strip()
    if "campaign" in data and data["campaign"] is not None:
        link.campaign = data["campaign"].strip() or "General"
    if "tags" in data and data["tags"] is not None:
        link.tags = ",".join(dict.fromkeys(t.strip() for t in data["tags"] if t.strip()))[:500]
    if "expires_at" in data:
        link.expires_at = data["expires_at"].replace(tzinfo=None) if data["expires_at"] else None
    if "click_cap" in data:
        link.click_cap = data["click_cap"]
    if "password" in data:
        link.password_hash = hash_password(data["password"]) if data["password"] else None
    db.commit()
    db.refresh(link)
    return serialize_link(link)

@app.post("/api/links/{link_id}/duplicate")
def duplicate_link(link_id: int, db: Session = Depends(get_db)):
    """Create a fresh link with the same destination and campaign metadata."""
    source = db.query(Link).filter(Link.id == link_id).first()
    if not source:
        raise HTTPException(404, "Link not found")
    clone = Link(
        short_code=make_code(db), destination_url=source.destination_url,
        campaign=source.campaign, tags=source.tags, expires_at=source.expires_at,
        click_cap=source.click_cap, password_hash=source.password_hash,
        status="active", total_clicks=0
    )
    db.add(clone)
    db.commit()
    db.refresh(clone)
    return serialize_link(clone)

@app.delete("/api/links/{link_id}")
def delete_link(link_id: int, db: Session = Depends(get_db)):
    """Permanently delete a link and its click history."""
    link = db.query(Link).filter(Link.id == link_id).first()
    if not link:
        raise HTTPException(404, "Link not found")
    db.delete(link)
    db.commit()
    return {"deleted": True, "id": link_id}

@app.post("/api/links/bulk")
def bulk_create_links(payload: BulkLinkCreate, db: Session = Depends(get_db)):
    """Create up to 100 short links in one request."""
    if len(payload.links) > 100:
        raise HTTPException(400, "A maximum of 100 links can be created at once.")
    created, errors = [], []
    for index, item in enumerate(payload.links, start=1):
        try:
            alias = item.alias.strip() if item.alias else None
            if alias and db.query(Link).filter(Link.short_code == alias).first():
                raise ValueError(f"Alias already exists: {alias}")
            link = Link(
                short_code=alias or make_code(db),
                destination_url=item.destination_url,
                campaign=item.campaign.strip() or "Bulk import",
                tags=",".join(dict.fromkeys(t.strip() for t in item.tags if t.strip()))[:500],
                password_hash=hash_password(item.password) if item.password else None,
                expires_at=item.expires_at.replace(tzinfo=None) if item.expires_at else None,
                click_cap=item.click_cap, status="active", total_clicks=0
            )
            db.add(link)
            db.flush()
            created.append(serialize_link(link))
        except Exception as exc:
            errors.append({"index": index, "error": str(exc)})
    db.commit()
    return {"created_count": len(created), "created": created, "errors": errors}

@app.get("/api/export/analytics.csv")
def export_analytics_csv(db: Session = Depends(get_db)):
    """Export click events with device, browser and referrer metadata."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["clicked_at", "short_code", "destination_url", "referrer", "device", "browser", "is_bot"])
    events = db.query(ClickEvent).join(Link).order_by(desc(ClickEvent.clicked_at)).all()
    for event in events:
        writer.writerow([
            event.clicked_at.isoformat(), event.link.short_code if event.link else "",
            event.link.destination_url if event.link else "", event.referrer or "Direct",
            event.device, event.browser, event.is_bot
        ])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=linkpulse-analytics.csv"})

@app.get("/api/links/{link_id}/qr")
def qr_code(link_id: int, db: Session = Depends(get_db)):
    link = db.query(Link).filter(Link.id == link_id).first()
    if not link: raise HTTPException(404, "Link not found")
    image = qrcode.make(f"{PUBLIC_BASE_URL}/{link.short_code}")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return Response(content=buffer.getvalue(), media_type="image/png",
                    headers={"Content-Disposition": f'attachment; filename="linkpulse-{link.short_code}.png"'})

@app.post("/api/import/csv")
async def import_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Upload a .csv file")
    raw = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(raw))
    created, errors = [], []
    for row_num, row in enumerate(reader, start=2):
        try:
            url = (row.get("destination_url") or "").strip()
            if not url.startswith(("http://", "https://")): raise ValueError("Invalid destination_url")
            alias = (row.get("alias") or "").strip() or None
            if alias and db.query(Link).filter(Link.short_code == alias).first(): raise ValueError("Alias already exists")
            expiry = None
            if row.get("expires_at"):
                expiry = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00")).replace(tzinfo=None)
            cap = int(row["click_cap"]) if row.get("click_cap", "").strip() else None
            link = Link(short_code=alias or make_code(db), destination_url=url,
                        campaign=(row.get("campaign") or "CSV Import")[:120],
                        tags=",".join(x.strip() for x in (row.get("tags") or "").split(",") if x.strip()),
                        expires_at=expiry, click_cap=cap,
                        password_hash=hash_password(row["password"]) if row.get("password") else None,
                        status="active", total_clicks=0)
            db.add(link); db.flush()
            created.append(serialize_link(link))
        except Exception as exc:
            errors.append({"row": row_num, "error": str(exc)})
    db.commit()
    return {"created_count": len(created), "created": created, "errors": errors}

@app.get("/api/export/csv")
def export_csv(db: Session = Depends(get_db)):
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["short_code", "short_url", "destination_url", "campaign", "tags", "status", "total_clicks", "created_at"])
    for link in db.query(Link).order_by(desc(Link.created_at)).all():
        writer.writerow([link.short_code, f"{PUBLIC_BASE_URL}/{link.short_code}", link.destination_url,
                         link.campaign, link.tags, link.status, link.total_clicks, link.created_at.isoformat()])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=linkpulse-links.csv"})

@app.get("/{short_code}")
def redirect_short(short_code: str, request: Request, background_tasks: BackgroundTasks,
                   password: Optional[str] = None, db: Session = Depends(get_db)):
    # Keep API paths out of short-code routing.
    if short_code == "favicon.ico": raise HTTPException(404, "Not found")
    link = db.query(Link).filter(Link.short_code == short_code).first()
    if not link: raise HTTPException(404, "This short link does not exist.")
    now = utcnow()
    if link.status != "active": raise HTTPException(410, "This link has been disabled by its owner.")
    if link.expires_at and link.expires_at <= now: raise HTTPException(410, "This link has expired.")
    if link.click_cap is not None and link.total_clicks >= link.click_cap: raise HTTPException(410, "This link reached its click limit.")
    if link.password_hash:
        if not password or not verify_password(password, link.password_hash):
            raise HTTPException(401, "This link is password protected. Add ?password=YOUR_PASSWORD to the URL.")
    user_agent = request.headers.get("user-agent", "")
    referrer = request.headers.get("referer", "Direct")
    visitor = request.cookies.get("lp_visitor") or secrets.token_hex(12)
    background_tasks.add_task(save_click, link.id, referrer, user_agent, visitor)
    response = RedirectResponse(link.destination_url, status_code=302)
    response.set_cookie("lp_visitor", visitor, max_age=60*60*24*365, httponly=True, samesite="lax")
    return response
