from datetime import datetime, timezone
from typing import Optional
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.schemas.workout import CreateWorkoutRequest


def _serialize(doc: dict) -> dict:
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


async def _validate_exercises(db: AsyncIOMotorDatabase, exercises) -> Optional[str]:
    """Returns an error message if any exercise_id is invalid, else None."""
    for entry in exercises:
        try:
            oid = ObjectId(entry.exercise_id)
        except Exception:
            return f"Invalid exercise_id format: {entry.exercise_id}"
        if not await db.exercises.find_one({"_id": oid}, {"_id": 1}):
            return f"Exercise '{entry.exercise_id}' not found in catalog"
    return None


async def list_workouts(
    db: AsyncIOMotorDatabase,
    *,
    user_id:  str,
    category: Optional[str],
    skip:     int,
    limit:    int,
) -> dict:
    pipeline: list = []

    if category:
        pipeline += [
            {"$match": {"user_id": user_id}},
            {"$lookup": {"from": "exercises", "localField": "exercises.exercise_id",
                         "foreignField": "_id", "as": "_ex"}},
            {"$match": {"_ex.category": category}},
            {"$project": {"_ex": 0}},
        ]
    else:
        pipeline.append({"$match": {"user_id": user_id}})

    pipeline += [{"$sort": {"date": -1}}, {"$skip": skip}, {"$limit": limit}]

    cursor   = db.workouts.aggregate(pipeline)
    data     = [_serialize(doc) async for doc in cursor]
    total    = await db.workouts.count_documents({"user_id": user_id})
    return {"total": total, "skip": skip, "limit": limit, "data": data}


async def get_workout(db: AsyncIOMotorDatabase, workout_id: str) -> dict | None:
    try:
        oid = ObjectId(workout_id)
    except Exception:
        return None
    doc = await db.workouts.find_one({"_id": oid})
    return _serialize(doc) if doc else None


async def create_workout(
    db: AsyncIOMotorDatabase, payload: CreateWorkoutRequest
) -> tuple[dict | None, str | None]:
    error = await _validate_exercises(db, payload.exercises)
    if error:
        return None, error

    doc = payload.model_dump()
    doc["date"]       = doc["date"] or datetime.now(timezone.utc)
    doc["created_at"] = datetime.now(timezone.utc)

    result  = await db.workouts.insert_one(doc)
    created = await db.workouts.find_one({"_id": result.inserted_id})
    return _serialize(created), None
