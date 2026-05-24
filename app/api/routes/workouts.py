from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from typing import Optional
from datetime import datetime, timezone, timedelta
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


@router.get("/home-stats", summary="Consolidated home screen stats for the logged-in user")
async def get_home_stats(
    current_user: dict       = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Returns in one call:
    - streak          : current consecutive-day workout streak
    - week            : which days this Mon–Sun week had workouts + count
    - personal_records: top-5 all-time best sets per exercise (by weight)
    """
    user_id = str(current_user["_id"])
    today   = datetime.now(timezone.utc).date()

    # ── 1. Fetch all workout dates (for streak + week dots) ───────────────────
    cursor = db.workouts.find({"user_id": user_id}, {"date": 1, "_id": 0})
    workout_dates: set = set()
    async for doc in cursor:
        d = doc.get("date")
        if isinstance(d, datetime):
            workout_dates.add(d.date())

    # ── 2. Streak ─────────────────────────────────────────────────────────────
    if today in workout_dates:
        streak_start = today
    elif (today - timedelta(days=1)) in workout_dates:
        streak_start = today - timedelta(days=1)
    else:
        streak_start = None

    streak = 0
    if streak_start:
        cur = streak_start
        while cur in workout_dates:
            streak += 1
            cur    -= timedelta(days=1)

    # ── 3. Current week dots (Mon=0 … Sun=6) ──────────────────────────────────
    monday = today - timedelta(days=today.weekday())
    completed_days = sorted({
        (d - monday).days
        for d in workout_dates
        if monday <= d <= today          # only days up to today
        and 0 <= (d - monday).days <= 6
    })

    # ── 4. Personal records — top-5 best sets per exercise by weight ──────────
    pr_pipeline = [
        {"$match": {"user_id": user_id}},
        {"$unwind": "$exercises"},
        {"$unwind": "$exercises.sets"},
        {"$match": {"exercises.sets.weight_kg": {"$gt": 0}}},
        # After this sort, $first picks the heaviest set for each exercise
        {"$sort": {"exercises.sets.weight_kg": -1}},
        {"$group": {
            "_id":             "$exercises.exercise_name",
            "best_weight_kg":  {"$first": "$exercises.sets.weight_kg"},
            "best_reps":       {"$first": "$exercises.sets.reps"},
        }},
        {"$sort": {"best_weight_kg": -1}},
        {"$limit": 5},
    ]
    pr_cursor = db.workouts.aggregate(pr_pipeline)
    personal_records = [
        {
            "exercise":       doc["_id"],
            "best_weight_kg": doc["best_weight_kg"],
            "best_reps":      doc.get("best_reps") or 0,
        }
        async for doc in pr_cursor
    ]

    return {
        "streak": streak,
        "week": {
            "completed_days":  completed_days,
            "workouts_done":   len(completed_days),
        },
        "personal_records": personal_records,
    }


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
