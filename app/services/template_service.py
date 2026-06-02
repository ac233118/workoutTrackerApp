from datetime import datetime, timezone, timedelta
from typing import Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.template import CreateTemplateRequest, MobileCreateTemplateRequest


# ─── Shared helpers ───────────────────────────────────────────────────────────

def _serialize(doc: dict) -> dict:
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def _validate_exercises(db: AsyncIOMotorDatabase, exercises) -> Optional[str]:
    for entry in exercises:
        try:
            oid = ObjectId(entry.exercise_id)
        except Exception:
            return f"Invalid exercise_id format: {entry.exercise_id}"
        if not await db.exercises.find_one({"_id": oid}, {"_id": 1}):
            return f"Exercise '{entry.exercise_id}' not found in catalog"
    return None


# ─── Full-featured template service (/templates) ──────────────────────────────

async def list_templates(
    db: AsyncIOMotorDatabase,
    *,
    program:    Optional[str],
    difficulty: Optional[str],
    is_public:  Optional[bool],
    created_by: Optional[str],
    skip:       int,
    limit:      int,
) -> dict:
    query: dict = {}
    if program:
        query["program"] = program
    if difficulty:
        query["difficulty"] = difficulty
    if is_public is not None:
        query["is_public"] = is_public
    if created_by:
        query["created_by"] = created_by

    cursor    = db.templates.find(query).skip(skip).limit(limit)
    data      = [_serialize(doc) async for doc in cursor]
    total     = await db.templates.count_documents(query)
    return {"total": total, "skip": skip, "limit": limit, "data": data}


async def get_template(db: AsyncIOMotorDatabase, template_id: str) -> dict | None:
    try:
        oid = ObjectId(template_id)
    except Exception:
        return None
    doc = await db.templates.find_one({"_id": oid})
    return _serialize(doc) if doc else None


async def create_template(
    db: AsyncIOMotorDatabase, payload: CreateTemplateRequest
) -> tuple[dict | None, str | None]:
    error = await _validate_exercises(db, payload.exercises)
    if error:
        return None, error

    doc = payload.model_dump()
    doc["created_at"] = datetime.now(timezone.utc)

    result  = await db.templates.insert_one(doc)
    created = await db.templates.find_one({"_id": result.inserted_id})
    return _serialize(created), None


async def start_workout_from_template(
    db: AsyncIOMotorDatabase, template_id: str, user_id: str
) -> tuple[dict | None, str | None]:
    try:
        oid = ObjectId(template_id)
    except Exception:
        return None, "invalid_id"

    tmpl = await db.templates.find_one({"_id": oid})
    if not tmpl:
        return None, "not_found"

    exercises = [
        {
            "exercise_id":         ex["exercise_id"],
            "exercise_name":       ex["exercise_name"],
            "order":               ex["order"],
            "sets":                [],
            "target_sets":         ex["target_sets"],
            "target_reps":         ex.get("target_reps"),
            "target_duration_sec": ex.get("target_duration_sec"),
            "rest_sec":            ex.get("rest_sec", 60),
            "notes":               ex.get("notes"),
        }
        for ex in tmpl.get("exercises", [])
    ]

    now = datetime.now(timezone.utc)
    doc = {
        "user_id":          user_id,
        "title":            tmpl["name"],
        "template_id":      str(tmpl["_id"]),
        "date":             now,
        "duration_minutes": None,
        "notes":            None,
        "exercises":        exercises,
        "created_at":       now,
    }

    result  = await db.workouts.insert_one(doc)
    created = await db.workouts.find_one({"_id": result.inserted_id})
    return _serialize(created), None


# ─── Mobile template service (/api/templates) ─────────────────────────────────

def _last_done_str(last_used_at: Optional[datetime]) -> str:
    if last_used_at is None:
        return "Never"
    now = datetime.now(timezone.utc)
    if last_used_at.tzinfo is None:
        last_used_at = last_used_at.replace(tzinfo=timezone.utc)
    delta = now - last_used_at
    if delta < timedelta(hours=24):
        return "Today"
    if delta < timedelta(hours=48):
        return "Yesterday"
    if delta < timedelta(days=7):
        return f"{delta.days} days ago"
    if delta < timedelta(days=30):
        weeks = delta.days // 7
        return f"{weeks} week{'s' if weeks > 1 else ''} ago"
    months = delta.days // 30
    return f"{months} month{'s' if months > 1 else ''} ago"


def _to_mobile_response(doc: dict) -> dict:
    return {
        "id":        doc["template_id"],
        "name":      doc["name"],
        "emoji":     doc["emoji"],
        "lastDone":  _last_done_str(doc.get("last_used_at")),
        "exercises": doc.get("exercise_names", [])[:6],
        "isCustom":  doc.get("user_id") is not None,
    }


async def _next_template_id(db: AsyncIOMotorDatabase) -> int:
    last = await db.templates.find_one(
        {}, {"template_id": 1}, sort=[("template_id", -1)]
    )
    return (last["template_id"] + 1) if last else 1


async def mobile_list_templates(
    db: AsyncIOMotorDatabase,
    user_id: Optional[str] = None,
) -> list[dict]:
    # Return system templates (user_id=None) + user's own templates
    if user_id:
        query = {
            "deleted_at": None,
            "$or": [{"user_id": None}, {"user_id": user_id}],
        }
    else:
        query = {"deleted_at": None, "user_id": None}

    cursor = db.templates.find(query).sort("template_id", 1)
    return [_to_mobile_response(doc) async for doc in cursor]


async def mobile_create_template(
    db: AsyncIOMotorDatabase,
    payload: MobileCreateTemplateRequest,
    user_id: str,
) -> dict:
    doc = {
        "template_id":    await _next_template_id(db),
        "name":           payload.name,
        "emoji":          payload.emoji,
        "exercise_names": payload.exercises[:10],
        "last_used_at":   None,
        "deleted_at":     None,
        "created_at":     datetime.now(timezone.utc),
        "user_id":        user_id,
    }
    await db.templates.insert_one(doc)
    return _to_mobile_response(doc)


async def mobile_mark_used(
    db: AsyncIOMotorDatabase, template_id: int
) -> bool:
    result = await db.templates.update_one(
        {"template_id": template_id, "deleted_at": None},
        {"$set": {"last_used_at": datetime.now(timezone.utc)}},
    )
    return result.matched_count > 0


async def mobile_delete_template(
    db: AsyncIOMotorDatabase,
    template_id: int,
    user_id: str,
) -> bool:
    # Only the owner can delete their custom template
    result = await db.templates.update_one(
        {"template_id": template_id, "deleted_at": None, "user_id": user_id},
        {"$set": {"deleted_at": datetime.now(timezone.utc)}},
    )
    return result.matched_count > 0
