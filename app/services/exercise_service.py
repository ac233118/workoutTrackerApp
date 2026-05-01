from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional
from bson import ObjectId


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
) -> dict:
    query: dict = {}
    if category:
        query["category"] = category
    if equipment:
        query["equipment"] = equipment
    if muscle_group:
        query["muscle_groups"] = muscle_group
    if difficulty:
        query["difficulty"] = difficulty

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
