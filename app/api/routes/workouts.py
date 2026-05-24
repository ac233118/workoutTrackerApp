from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import get_db
from app.core.dependencies import get_current_user
from app.schemas.workout import CreateWorkoutRequest
from app.services import workout_service
from app.services.pdf_service import generate_workout_pdf

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


@router.get("/{workout_id}/pdf", summary="Download a workout as a styled PDF")
async def download_workout_pdf(
    workout_id: str,
    current_user: dict       = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Generates and streams a styled A4 PDF report for a single workout.

    - 401 if no / invalid Bearer token
    - 403 if workout belongs to a different user
    - 404 if workout not found or invalid ID
    - 500 if PDF generation fails unexpectedly
    """
    # ── 1. Fetch workout ──────────────────────────────────────────────────────
    workout = await workout_service.get_workout(db, workout_id)
    if workout is None:
        raise HTTPException(status_code=404, detail="Workout not found")

    # ── 2. Ownership check ────────────────────────────────────────────────────
    if workout.get("user_id") != str(current_user["_id"]):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this workout",
        )

    # ── 3. Generate PDF ───────────────────────────────────────────────────────
    try:
        pdf_buf = generate_workout_pdf(workout)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"PDF generation failed: {str(exc)}",
        )

    # ── 4. Stream back to client ──────────────────────────────────────────────
    title = workout.get("title", "workout").replace(" ", "_").lower()
    filename = f"{title}_workout.pdf"

    return StreamingResponse(
        pdf_buf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
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
