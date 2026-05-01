from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import get_db
from app.services import exercise_service

router = APIRouter(prefix="/exercises", tags=["Exercises"])


@router.get("", summary="Browse the exercise catalog")
async def list_exercises(
    category:     Optional[str] = Query(None),
    equipment:    Optional[str] = Query(None),
    muscle_group: Optional[str] = Query(None),
    difficulty:   Optional[str] = Query(None),
    skip:         int           = Query(0,  ge=0),
    limit:        int           = Query(50, ge=1, le=200),
    db: AsyncIOMotorDatabase    = Depends(get_db),
):
    return await exercise_service.list_exercises(
        db,
        category=category,
        equipment=equipment,
        muscle_group=muscle_group,
        difficulty=difficulty,
        skip=skip,
        limit=limit,
    )


@router.get("/{exercise_id}", summary="Get a single exercise")
async def get_exercise(
    exercise_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    doc = await exercise_service.get_exercise_by_id(db, exercise_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Exercise not found")
    return doc
