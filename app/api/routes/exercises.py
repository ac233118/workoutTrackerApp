from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import get_db
from app.core.dependencies import get_current_user, get_optional_user
from app.services import exercise_service

router = APIRouter(prefix="/exercises", tags=["Exercises"])

VALID_DIFFICULTIES   = {"Beginner", "Intermediate", "Advanced"}
VALID_TRACKING_TYPES = {"weighted", "bodyweight", "timed", "weighted_timed"}


class CreateExerciseRequest(BaseModel):
    name:          str
    category:      str
    muscle_groups: list[str] = []
    equipment:     str       = "Other"
    difficulty:    str       = "Beginner"
    instructions:  str       = ""
    tracking_type: str       = "weighted"   # weighted | bodyweight | timed | weighted_timed


@router.get("", summary="Browse the exercise catalog (public + user's custom)")
async def list_exercises(
    category:     Optional[str] = Query(None),
    equipment:    Optional[str] = Query(None),
    muscle_group: Optional[str] = Query(None),
    difficulty:   Optional[str] = Query(None),
    skip:         int           = Query(0,  ge=0),
    limit:        int           = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase    = Depends(get_db),
    current_user: Optional[dict] = Depends(get_optional_user),
):
    user_id = str(current_user["_id"]) if current_user else None
    return await exercise_service.list_exercises(
        db,
        category=category,
        equipment=equipment,
        muscle_group=muscle_group,
        difficulty=difficulty,
        skip=skip,
        limit=limit,
        user_id=user_id,
    )


@router.post("", status_code=201, summary="Create a custom exercise (visible only to you)")
async def create_exercise(
    payload:      CreateExerciseRequest,
    db:           AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict                 = Depends(get_current_user),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Exercise name is required")
    if payload.difficulty not in VALID_DIFFICULTIES:
        raise HTTPException(status_code=400, detail=f"difficulty must be one of {VALID_DIFFICULTIES}")
    if payload.tracking_type not in VALID_TRACKING_TYPES:
        raise HTTPException(status_code=400, detail=f"tracking_type must be one of {VALID_TRACKING_TYPES}")

    # Prevent duplicates for this user
    existing = await db.exercises.find_one({
        "name":    {"$regex": f"^{name}$", "$options": "i"},
        "$or": [{"user_id": {"$exists": False}}, {"user_id": None}, {"user_id": str(current_user["_id"])}],
    })
    if existing:
        raise HTTPException(status_code=409, detail="An exercise with this name already exists")

    doc = await exercise_service.create_custom_exercise(
        db,
        user_id       = str(current_user["_id"]),
        name          = name,
        category      = payload.category.strip() or "Other",
        muscle_groups = payload.muscle_groups,
        equipment     = payload.equipment.strip() or "Other",
        difficulty    = payload.difficulty,
        instructions  = payload.instructions.strip(),
        tracking_type = payload.tracking_type,
    )
    return doc


@router.delete("/{exercise_id}", status_code=204, summary="Delete your custom exercise")
async def delete_exercise(
    exercise_id:  str,
    db:           AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict                 = Depends(get_current_user),
):
    deleted = await exercise_service.delete_custom_exercise(
        db, exercise_id=exercise_id, user_id=str(current_user["_id"])
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Exercise not found or not yours to delete")


@router.get("/{exercise_id}", summary="Get a single exercise")
async def get_exercise(
    exercise_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    doc = await exercise_service.get_exercise_by_id(db, exercise_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return doc
