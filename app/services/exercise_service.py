from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional
from bson import ObjectId
from datetime import datetime, timezone


def _serialize(doc: dict) -> dict:
    doc["id"] = str(doc.pop("_id"))
    return doc


async def list_exercises(
    db: AsyncIOMotorDatabase,
    *,
    category:     Optional[str],
    equipment:    Optional[str],
    muscle_group: Optional[str],
    difficulty:   Optional[str],
    skip:         int,
    limit:        int,
    user_id:      Optional[str] = None,
) -> dict:
    # Base filter: public exercises (no user_id field) OR user's custom ones
    if user_id:
        ownership = {"$or": [{"user_id": {"$exists": False}}, {"user_id": None}, {"user_id": user_id}]}
    else:
        ownership = {"$or": [{"user_id": {"$exists": False}}, {"user_id": None}]}

    query: dict = {"$and": [ownership]}
    if category:
        query["$and"].append({"category": category})
    if equipment:
        query["$and"].append({"equipment": equipment})
    if muscle_group:
        query["$and"].append({"muscle_groups": muscle_group})
    if difficulty:
        query["$and"].append({"difficulty": difficulty})

    # Flatten single-element $and
    if len(query["$and"]) == 1:
        query = query["$and"][0]

    cursor = db.exercises.find(query).skip(skip).limit(limit)
    data   = [_serialize(doc) async for doc in cursor]
    total  = await db.exercises.count_documents(query)
    return {"total": total, "skip": skip, "limit": limit, "data": data}


async def get_exercise_by_id(db: AsyncIOMotorDatabase, exercise_id: str) -> dict | None:
    try:
        oid = ObjectId(exercise_id)
    except Exception:
        return None
    doc = await db.exercises.find_one({"_id": oid})
    return _serialize(doc) if doc else None


async def create_custom_exercise(
    db: AsyncIOMotorDatabase,
    *,
    user_id:       str,
    name:          str,
    category:      str,
    muscle_groups: list[str],
    equipment:     str,
    difficulty:    str,
    instructions:  str,
) -> dict:
    doc = {
        "name":          name,
        "category":      category,
        "muscle_groups": muscle_groups,
        "equipment":     equipment,
        "difficulty":    difficulty,
        "instructions":  instructions,
        "user_id":       user_id,       # marks this as a custom exercise
        "created_at":    datetime.now(timezone.utc),
    }
    result  = await db.exercises.insert_one(doc)
    created = await db.exercises.find_one({"_id": result.inserted_id})
    return _serialize(created)


async def delete_custom_exercise(
    db: AsyncIOMotorDatabase,
    exercise_id: str,
    user_id: str,
) -> bool:
    """Returns True if deleted, False if not found or not owned by user."""
    try:
        oid = ObjectId(exercise_id)
    except Exception:
        return False
    result = await db.exercises.delete_one({"_id": oid, "user_id": user_id})
    return result.deleted_count == 1
