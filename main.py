from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
from bson import ObjectId
import os
import certifi

MONGO_URL = os.getenv("MONGO_URL", "mongodb+srv://ac233118_db_user:17qflwYMttMouAAT@cluster0.wkkhjwa.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
DB_NAME   = os.getenv("DB_NAME", "Mistari")

# Detect Atlas (SRV) connections vs local so we only apply TLS settings when needed.
IS_ATLAS = "mongodb+srv://" in MONGO_URL or "mongodb.net" in MONGO_URL


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ──────────────────────────────────────────────
    if IS_ATLAS:
        # Use certifi's CA bundle — fixes CERTIFICATE_VERIFY_FAILED on macOS/Linux/Windows.
        app.state.client = AsyncIOMotorClient(
            MONGO_URL,
            tls=True,
            tlsCAFile=certifi.where(),
        )
    else:
        app.state.client = AsyncIOMotorClient(MONGO_URL)

    app.state.db = app.state.client[DB_NAME]
    yield
    # ── shutdown ─────────────────────────────────────────────
    app.state.client.close()


app = FastAPI(title="Workout Tracker API", version="1.0.0", lifespan=lifespan)


def db():
    return app.state.db


# ─── Helpers ────────────────────────────────────────────────────────────────

def to_str_id(doc: dict) -> dict:
    """Convert ObjectId fields to strings for JSON serialisation."""
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


# ─── Schemas ─────────────────────────────────────────────────────────────────

class SetEntry(BaseModel):
    set_number: int
    reps: Optional[int] = None
    weight_kg: Optional[float] = None
    duration_sec: Optional[int] = None
    rest_sec: Optional[int] = 60


class ExerciseEntry(BaseModel):
    exercise_id: str = Field(..., description="_id of the exercise from the exercises collection")
    exercise_name: str = Field(..., description="Denormalised name snapshot")
    order: int = Field(..., ge=1, description="Position of this exercise in the workout")
    sets: list[SetEntry] = Field(..., min_length=1)


class CreateWorkoutRequest(BaseModel):
    user_id: str
    title: str
    date: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    notes: Optional[str] = None
    exercises: list[ExerciseEntry] = Field(..., min_length=1)


# ─── GET /workouts ────────────────────────────────────────────────────────────

@app.get("/workouts", summary="List workouts for a user")
async def get_workouts(
    user_id: str = Query(..., description="Filter workouts by user"),
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    category: Optional[str] = Query(None, description="Filter by exercise category (e.g. Chest)"),
):
    """
    Returns paginated workouts for a user, newest first.
    Optionally filter by exercise category embedded in the workout.
    """
    pipeline = []

    match_stage: dict = {"user_id": user_id}

    if category:
        # Only include workouts that contain at least one exercise of the given category.
        # We do a lookup to the exercises collection to check.
        pipeline += [
            {"$match": match_stage},
            {
                "$lookup": {
                    "from": "exercises",
                    "localField": "exercises.exercise_id",
                    "foreignField": "_id",
                    "as": "_exercise_docs",
                }
            },
            {
                "$match": {
                    "_exercise_docs.category": category
                }
            },
            {"$project": {"_exercise_docs": 0}},
        ]
    else:
        pipeline.append({"$match": match_stage})

    pipeline += [
        {"$sort": {"date": -1}},
        {"$skip": skip},
        {"$limit": limit},
    ]

    cursor = db().workouts.aggregate(pipeline)
    workouts = [to_str_id(doc) async for doc in cursor]

    total = await db().workouts.count_documents({"user_id": user_id})

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "data": workouts,
    }


# ─── GET /workouts/{workout_id} ───────────────────────────────────────────────

@app.get("/workouts/{workout_id}", summary="Get a single workout by ID")
async def get_workout(workout_id: str):
    try:
        oid = ObjectId(workout_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid workout_id format")

    doc = await db().workouts.find_one({"_id": oid})
    if not doc:
        raise HTTPException(status_code=404, detail="Workout not found")

    return to_str_id(doc)


# ─── POST /workouts ───────────────────────────────────────────────────────────

@app.post("/workouts", status_code=201, summary="Create a new workout")
async def create_workout(payload: CreateWorkoutRequest):
    """
    Creates a workout session.

    Each exercise entry must reference a valid exercise_id from the exercises
    collection. The exercise_name is stored as a snapshot (denormalised) so
    historical records remain accurate even if the catalog is updated later.
    """
    # Validate that every exercise_id exists in the catalog
    for entry in payload.exercises:
        try:
            oid = ObjectId(entry.exercise_id)
        except Exception:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid exercise_id format: {entry.exercise_id}",
            )
        exists = await db().exercises.find_one({"_id": oid}, {"_id": 1})
        if not exists:
            raise HTTPException(
                status_code=404,
                detail=f"Exercise '{entry.exercise_id}' not found in catalog",
            )

    doc = payload.model_dump()
    doc["date"] = doc["date"] or datetime.now(timezone.utc)
    doc["created_at"] = datetime.now(timezone.utc)

    result = await db().workouts.insert_one(doc)
    created = await db().workouts.find_one({"_id": result.inserted_id})
    return to_str_id(created)


# ─── GET /exercises ───────────────────────────────────────────────────────────

@app.get("/exercises", summary="Browse the exercise catalog")
async def get_exercises(
    category: Optional[str] = Query(None),
    equipment: Optional[str] = Query(None),
    muscle_group: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    """Returns exercises filtered by category, equipment, muscle group, or difficulty."""
    query: dict = {}
    if category:
        query["category"] = category
    if equipment:
        query["equipment"] = equipment
    if muscle_group:
        query["muscle_groups"] = muscle_group
    if difficulty:
        query["difficulty"] = difficulty

    cursor = db().exercises.find(query).skip(skip).limit(limit)
    exercises = [to_str_id(doc) async for doc in cursor]
    total = await db().exercises.count_documents(query)

    return {"total": total, "skip": skip, "limit": limit, "data": exercises}