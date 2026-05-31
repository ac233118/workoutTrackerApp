from fastapi import APIRouter, Depends
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import get_db
from app.core.dependencies import get_current_user

router = APIRouter(prefix="/progress", tags=["Progress"])


@router.get("", summary="Progress stats by exercise and muscle group")
async def get_progress(
    current_user: dict       = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Returns two views of the user's training progress:

    by_exercise  — per-exercise: PR (best weight × reps), total sets,
                   total volume, and 8-week weekly volume trend
    by_muscle    — per-muscle-group: total sets, total volume,
                   number of distinct exercises, last trained date
    """
    user_id  = str(current_user["_id"])
    today    = datetime.now(timezone.utc).date()
    week_start = today - timedelta(days=today.weekday())          # Mon of this week
    eight_weeks_ago = week_start - timedelta(weeks=7)             # 8 weeks total

    # ── 1. by_exercise ────────────────────────────────────────────────────────
    # For each exercise: PR set, lifetime totals, 8-week weekly trend
    exercise_pipeline = [
        {"$match": {"user_id": user_id}},
        {"$unwind": "$exercises"},
        {"$unwind": "$exercises.sets"},
        {"$match": {"exercises.sets.weight_kg": {"$gt": 0}}},
        {"$addFields": {
            # Week bucket: ISO string "YYYY-Www" for grouping
            "week_offset": {
                "$floor": {
                    "$divide": [
                        {"$subtract": ["$date", datetime(eight_weeks_ago.year, eight_weeks_ago.month, eight_weeks_ago.day, tzinfo=timezone.utc)]},
                        1000 * 60 * 60 * 24 * 7,
                    ]
                }
            },
        }},
        {"$group": {
            "_id":             "$exercises.exercise_name",
            # PR: best weight × reps
            "best_weight_kg":  {"$max": "$exercises.sets.weight_kg"},
            "total_sets":      {"$sum": 1},
            "total_volume_kg": {"$sum": {"$multiply": [
                {"$ifNull": ["$exercises.sets.weight_kg", 0]},
                {"$ifNull": ["$exercises.sets.reps", 0]},
            ]}},
            # Collect (week_offset, volume) pairs for the trend
            "weekly_sets_raw": {"$push": {
                "w":   "$week_offset",
                "vol": {"$multiply": [
                    {"$ifNull": ["$exercises.sets.weight_kg", 0]},
                    {"$ifNull": ["$exercises.sets.reps", 0]},
                ]},
            }},
            # Grab reps from the heaviest set (approximation via sort not possible here,
            # so we collect all and pick post-aggregation)
            "all_reps_at_max": {"$push": {
                "w": "$exercises.sets.weight_kg",
                "r": "$exercises.sets.reps",
            }},
        }},
        {"$sort": {"total_volume_kg": -1}},
        {"$limit": 20},
    ]

    ex_cursor = db.workouts.aggregate(exercise_pipeline)
    by_exercise = []
    async for doc in ex_cursor:
        # Build 8-week trend (weeks 0–7, 0 = 8 weeks ago)
        weekly_vol: dict[int, float] = {i: 0.0 for i in range(8)}
        for item in doc["weekly_sets_raw"]:
            w = int(item["w"])
            if 0 <= w <= 7:
                weekly_vol[w] = weekly_vol.get(w, 0.0) + item["vol"]
        trend = [round(weekly_vol[i], 1) for i in range(8)]

        # Best reps at PR weight
        max_w = doc["best_weight_kg"]
        best_reps = max(
            (r["r"] for r in doc["all_reps_at_max"] if r["w"] == max_w and r["r"]),
            default=0,
        )

        by_exercise.append({
            "exercise":        doc["_id"],
            "pr_weight_kg":    max_w,
            "pr_reps":         best_reps,
            "total_sets":      doc["total_sets"],
            "total_volume_kg": round(doc["total_volume_kg"], 1),
            "weekly_volume_trend": trend,   # list[float], index 0 = 8 weeks ago
        })

    # ── 2. by_muscle ──────────────────────────────────────────────────────────
    # exercise_name is already denormalized on every workout exercise, so
    # look up the catalog by name — avoids ObjectId conversion issues entirely.
    muscle_pipeline = [
        {"$match": {"user_id": user_id}},
        {"$unwind": "$exercises"},
        {"$unwind": "$exercises.sets"},
        {"$lookup": {
            "from": "exercises",
            "let":  {"ex_name": "$exercises.exercise_name"},
            "pipeline": [
                {"$match": {"$expr": {"$eq": ["$name", "$$ex_name"]}}},
                {"$project": {"category": 1, "_id": 0}},
            ],
            "as": "catalog",
        }},
        {"$addFields": {
            "muscle_group": {
                "$ifNull": [
                    {"$arrayElemAt": ["$catalog.category", 0]},
                    "Other",
                ]
            }
        }},
        {"$group": {
            "_id":              "$muscle_group",
            "total_sets":       {"$sum": 1},
            "total_volume_kg":  {"$sum": {"$multiply": [
                {"$ifNull": ["$exercises.sets.weight_kg", 0]},
                {"$ifNull": ["$exercises.sets.reps", 0]},
            ]}},
            "distinct_exercises": {"$addToSet": "$exercises.exercise_name"},
            "last_trained":     {"$max": "$date"},
        }},
        {"$sort": {"total_volume_kg": -1}},
    ]

    mu_cursor = db.workouts.aggregate(muscle_pipeline)
    by_muscle = []
    async for doc in mu_cursor:
        last = doc["last_trained"]
        last_str = last.strftime("%Y-%m-%d") if isinstance(last, datetime) else None
        by_muscle.append({
            "muscle_group":      doc["_id"],
            "total_sets":        doc["total_sets"],
            "total_volume_kg":   round(doc["total_volume_kg"], 1),
            "exercise_count":    len(doc["distinct_exercises"]),
            "last_trained":      last_str,
        })

    return {
        "by_exercise": by_exercise,
        "by_muscle":   by_muscle,
    }
