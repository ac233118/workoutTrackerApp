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
    # Look up tracking_type for all exercises in catalog
    ex_type_map: dict[str, str] = {}
    async for ex in db.exercises.find({}, {"name": 1, "tracking_type": 1}):
        ex_type_map[ex["name"]] = ex.get("tracking_type", "weighted")

    exercise_pipeline = [
        {"$match": {"user_id": user_id}},
        {"$unwind": "$exercises"},
        {"$unwind": "$exercises.sets"},
        {"$addFields": {
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
            "_id":        "$exercises.exercise_name",
            "total_sets": {"$sum": 1},
            "all_sets_raw": {"$push": {
                "w":   "$week_offset",
                "weight_kg":    "$exercises.sets.weight_kg",
                "reps":         "$exercises.sets.reps",
                "duration_sec": "$exercises.sets.duration_sec",
            }},
        }},
        {"$sort": {"total_sets": -1}},
        {"$limit": 20},
    ]

    ex_cursor = db.workouts.aggregate(exercise_pipeline)
    by_exercise = []
    async for doc in ex_cursor:
        ex_name = doc["_id"]
        tt      = ex_type_map.get(ex_name, "weighted")
        sets    = doc["all_sets_raw"]

        weekly_vol: dict[int, float] = {i: 0.0 for i in range(8)}

        if tt == "weighted":
            valid = [s for s in sets if s.get("weight_kg") and s["weight_kg"] > 0]
            if not valid: continue
            for s in valid:
                w = int(s["w"]) if s.get("w") is not None else -1
                if 0 <= w <= 7:
                    weekly_vol[w] += (s["weight_kg"] or 0) * (s.get("reps") or 0)
            max_w     = max(s["weight_kg"] for s in valid)
            best_reps = max((s.get("reps", 0) for s in valid if s["weight_kg"] == max_w), default=0)
            pr = {"pr_weight_kg": max_w, "pr_reps": best_reps}
            total_vol = sum((s["weight_kg"] or 0) * (s.get("reps") or 0) for s in valid)

        elif tt == "bodyweight":
            valid = [s for s in sets if s.get("reps") and s["reps"] > 0]
            if not valid: continue
            for s in valid:
                w = int(s["w"]) if s.get("w") is not None else -1
                if 0 <= w <= 7:
                    weekly_vol[w] += s.get("reps") or 0
            pr = {"pr_reps": max(s["reps"] for s in valid)}
            total_vol = sum(s.get("reps", 0) for s in valid)

        elif tt == "timed":
            valid = [s for s in sets if s.get("duration_sec") and s["duration_sec"] > 0]
            if not valid: continue
            for s in valid:
                w = int(s["w"]) if s.get("w") is not None else -1
                if 0 <= w <= 7:
                    weekly_vol[w] += s.get("duration_sec") or 0
            pr = {"pr_duration_sec": max(s["duration_sec"] for s in valid)}
            total_vol = sum(s.get("duration_sec", 0) for s in valid)

        elif tt == "weighted_timed":
            valid = [s for s in sets if s.get("weight_kg") and s["weight_kg"] > 0]
            if not valid: continue
            for s in valid:
                w = int(s["w"]) if s.get("w") is not None else -1
                if 0 <= w <= 7:
                    weekly_vol[w] += (s["weight_kg"] or 0) * (s.get("duration_sec") or 0)
            max_w    = max(s["weight_kg"] for s in valid)
            best_dur = max((s.get("duration_sec", 0) for s in valid if s["weight_kg"] == max_w), default=0)
            pr = {"pr_weight_kg": max_w, "pr_duration_sec": best_dur}
            total_vol = sum((s["weight_kg"] or 0) * (s.get("duration_sec") or 0) for s in valid)

        else:
            continue

        trend = [round(weekly_vol[i], 1) for i in range(8)]
        by_exercise.append({
            "exercise":            ex_name,
            "tracking_type":       tt,
            "total_sets":          doc["total_sets"],
            "total_volume":        round(total_vol, 1),
            "weekly_volume_trend": trend,
            **pr,
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


@router.get("/exercise-prs", summary="PR for a list of exercise names")
async def get_exercise_prs(
    names: str,                              # comma-separated exercise names
    current_user: dict       = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Returns the PR for each requested exercise name, shaped by tracking_type:
      weighted       → { tracking_type, weight_kg, reps }
      bodyweight     → { tracking_type, reps }
      timed          → { tracking_type, duration_sec }
      weighted_timed → { tracking_type, weight_kg, duration_sec }
    Exercises with no history are omitted.
    """
    user_id   = str(current_user["_id"])
    name_list = [n.strip() for n in names.split(",") if n.strip()]

    # Look up tracking_type for each exercise from the catalog
    type_map: dict[str, str] = {}
    async for ex in db.exercises.find(
        {"name": {"$in": name_list}},
        {"name": 1, "tracking_type": 1},
    ):
        type_map[ex["name"]] = ex.get("tracking_type", "weighted")

    # Aggregate all sets for these exercises
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$unwind": "$exercises"},
        {"$match": {"exercises.exercise_name": {"$in": name_list}}},
        {"$unwind": "$exercises.sets"},
        {"$group": {
            "_id":      "$exercises.exercise_name",
            "all_sets": {"$push": {
                "weight_kg":    "$exercises.sets.weight_kg",
                "reps":         "$exercises.sets.reps",
                "duration_sec": "$exercises.sets.duration_sec",
            }},
        }},
    ]

    result: dict[str, dict] = {}
    async for doc in db.workouts.aggregate(pipeline):
        ex_name  = doc["_id"]
        tt       = type_map.get(ex_name, "weighted")
        sets     = doc["all_sets"]

        if tt == "weighted":
            valid = [s for s in sets if s.get("weight_kg") and s["weight_kg"] > 0]
            if not valid: continue
            max_w = max(s["weight_kg"] for s in valid)
            best_reps = max((s["reps"] for s in valid if s["weight_kg"] == max_w and s.get("reps")), default=0)
            result[ex_name] = {"tracking_type": tt, "weight_kg": max_w, "reps": best_reps}

        elif tt == "bodyweight":
            valid = [s for s in sets if s.get("reps") and s["reps"] > 0]
            if not valid: continue
            result[ex_name] = {"tracking_type": tt, "reps": max(s["reps"] for s in valid)}

        elif tt == "timed":
            valid = [s for s in sets if s.get("duration_sec") and s["duration_sec"] > 0]
            if not valid: continue
            result[ex_name] = {"tracking_type": tt, "duration_sec": max(s["duration_sec"] for s in valid)}

        elif tt == "weighted_timed":
            valid = [s for s in sets if s.get("weight_kg") and s["weight_kg"] > 0]
            if not valid: continue
            max_w = max(s["weight_kg"] for s in valid)
            best_dur = max((s.get("duration_sec", 0) for s in valid if s["weight_kg"] == max_w), default=0)
            result[ex_name] = {"tracking_type": tt, "weight_kg": max_w, "duration_sec": best_dur}

    return result


@router.get("/muscle/{muscle_group}", summary="Muscle group detail — weekly trend + sub-muscle breakdown")
async def get_muscle_detail(
    muscle_group: str,
    current_user: dict       = Depends(get_current_user),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Returns:
      weekly_trend  — 12-week volume trend (oldest → newest)
      sub_muscles   — per-sub-muscle: total sets + volume
    """
    user_id = str(current_user["_id"])
    today   = datetime.now(timezone.utc).date()
    week_start = today - timedelta(days=today.weekday())
    twelve_weeks_ago = week_start - timedelta(weeks=11)
    base_date = datetime(
        twelve_weeks_ago.year, twelve_weeks_ago.month, twelve_weeks_ago.day,
        tzinfo=timezone.utc,
    )

    # Steps shared by both sub-pipelines:
    # unwind → lookup catalog → filter by this muscle_group
    common_steps = [
        {"$match": {"user_id": user_id}},
        {"$unwind": "$exercises"},
        {"$unwind": "$exercises.sets"},
        {"$lookup": {
            "from": "exercises",
            "let":  {"ex_name": "$exercises.exercise_name"},
            "pipeline": [
                {"$match": {"$expr": {"$eq": ["$name", "$$ex_name"]}}},
                {"$project": {"category": 1, "muscle_groups": 1, "_id": 0}},
            ],
            "as": "catalog",
        }},
        {"$addFields": {
            "cat_doc": {"$arrayElemAt": ["$catalog", 0]},
        }},
        {"$addFields": {
            "muscle_group":      {"$ifNull": ["$cat_doc.category",      "Other"]},
            "sub_muscle_groups": {"$ifNull": ["$cat_doc.muscle_groups", []]},
        }},
        {"$match": {"muscle_group": muscle_group}},
    ]

    # ── 1. Weekly volume trend (12 weeks) ─────────────────────────────────────
    trend_pipeline = common_steps + [
        {"$match": {"date": {"$gte": base_date}}},
        {"$addFields": {
            "week_offset": {
                "$floor": {
                    "$divide": [
                        {"$subtract": ["$date", base_date]},
                        1000 * 60 * 60 * 24 * 7,
                    ]
                }
            },
            "set_vol": {
                "$multiply": [
                    {"$ifNull": ["$exercises.sets.weight_kg", 0]},
                    {"$ifNull": ["$exercises.sets.reps",      0]},
                ]
            },
        }},
        {"$group": {
            "_id":        "$week_offset",
            "volume_kg":  {"$sum": "$set_vol"},
            # Collect (date, workout_id) pairs so we can sort by date
            "workouts":   {"$addToSet": {"id": {"$toString": "$_id"}, "date": "$date"}},
        }},
        {"$sort": {"_id": 1}},
    ]

    week_vol:        dict[int, float]     = {i: 0.0  for i in range(12)}
    week_workout_ids: dict[int, list[str]] = {i: []   for i in range(12)}
    async for doc in db.workouts.aggregate(trend_pipeline):
        w = int(doc["_id"])
        if 0 <= w <= 11:
            week_vol[w] = round(doc["volume_kg"], 1)
            # Sort workouts newest-first so index 0 = most recent
            sorted_wk = sorted(doc["workouts"], key=lambda x: x["date"], reverse=True)
            week_workout_ids[w] = [x["id"] for x in sorted_wk]

    weekly_trend = []
    for i in range(12):
        week_date = twelve_weeks_ago + timedelta(weeks=i)
        weekly_trend.append({
            "week_label":  week_date.strftime("%b %d"),
            "volume_kg":   week_vol[i],
            "workout_ids": week_workout_ids[i],   # newest first
        })

    # ── 2. Sub-muscle breakdown ───────────────────────────────────────────────
    sub_pipeline = common_steps + [
        {"$unwind": {"path": "$sub_muscle_groups", "preserveNullAndEmptyArrays": False}},
        {"$group": {
            "_id":            "$sub_muscle_groups",
            "total_sets":     {"$sum": 1},
            "total_volume_kg": {"$sum": {
                "$multiply": [
                    {"$ifNull": ["$exercises.sets.weight_kg", 0]},
                    {"$ifNull": ["$exercises.sets.reps",      0]},
                ]
            }},
        }},
        {"$sort": {"total_volume_kg": -1}},
    ]

    sub_muscles = []
    async for doc in db.workouts.aggregate(sub_pipeline):
        sub_muscles.append({
            "name":            doc["_id"],
            "total_sets":      doc["total_sets"],
            "total_volume_kg": round(doc["total_volume_kg"], 1),
        })

    return {
        "muscle_group": muscle_group,
        "weekly_trend": weekly_trend,
        "sub_muscles":  sub_muscles,
    }
