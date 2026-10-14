from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.auth import get_current_user
from backend.db.database import get_db
from backend.db.models import SIGNALS
from backend.db.supabase import SupabaseDB
from backend.middleware.rate_limiter import check_rate_limit
from backend.services import learn_service

router = APIRouter(prefix="/api/learn", tags=["learn"])


class ChatMessage(BaseModel):
    role: str = Field("user", pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=4000)


class TutorIn(BaseModel):
    messages: list[ChatMessage] = Field(default_factory=list)


class ExplainIn(BaseModel):
    signal_id: str | None = None
    signal: dict | None = None


@router.get("/status")
async def status(user: dict = Depends(get_current_user)):
    return learn_service.status()


@router.get("/lessons")
async def lessons(user: dict = Depends(get_current_user)):
    return {"lessons": learn_service.lesson_index(), "disclaimer": learn_service.DISCLAIMER}


@router.get("/lessons/{slug}")
async def lesson(slug: str, user: dict = Depends(get_current_user)):
    item = learn_service.get_lesson(slug)
    if not item:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return item


@router.get("/glossary")
async def glossary(user: dict = Depends(get_current_user)):
    return {"terms": learn_service.GLOSSARY}


@router.get("/quiz")
async def quiz(user: dict = Depends(get_current_user)):
    return {"questions": learn_service.all_quiz()}


@router.post("/tutor")
async def tutor(body: TutorIn, user: dict = Depends(get_current_user)):
    check_rate_limit(user["id"], user.get("tier", "free"))
    messages = [m.model_dump() for m in body.messages]
    return await learn_service.tutor(messages, user)


@router.post("/explain-signal")
async def explain_signal(
    body: ExplainIn,
    db: SupabaseDB = Depends(get_db),
    user: dict = Depends(get_current_user),
):
    check_rate_limit(user["id"], user.get("tier", "free"))
    signal = body.signal
    if signal is None and body.signal_id:
        signal = await db.fetch_one(SIGNALS, {"id": body.signal_id})
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    return await learn_service.explain_signal(signal, user)
