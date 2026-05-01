from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import get_db
from app.schemas.workout import CreateWorkoutRequest
from app.services import workout_service

router = APIRouter(prefix="/workouts", tags=["Workouts"])


@router.get("", summary="List workouts for a user")
async def list_workouts(
    user_id:  str           = Query(..., description="Filter workouts by user"),
    category: Optional[str] = Query(None, description="Filter by exercise category e.g. Chest"),
    skip:     int           = Query(0,  ge=0),
    limit:    int           = Query(20, ge=1, le=100),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    return await workout_service.list_workouts(
        db, user_id=user_id, category=category, skip=skip, limit=limit
    )


@router.get("/{workout_id}", summary="Get a single workout")
async def get_workout(
    workout_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    doc = await workout_service.get_workout(db, workout_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Workout not found")
    return doc


@router.post("", status_code=201, summary="Create a new workout")
async def create_workout(
    payload: CreateWorkoutRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    doc, error = await workout_service.create_workout(db, payload)
    if error:
        status = 400 if "format" in error else 404
        raise HTTPException(status_code=status, detail=error)
    return doc
