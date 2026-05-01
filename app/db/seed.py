from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

_TEMPLATE_SEED = [
    {"template_id": 1, "name": "Push Day", "emoji": "💪",
     "exercise_names": ["Barbell bench press", "Overhead press", "Triceps dip", "Incline dumbbell press"]},
    {"template_id": 2, "name": "Pull Day", "emoji": "🔙",
     "exercise_names": ["Pull-up", "Bent-over row", "Dumbbell curl", "Hammer curl"]},
    {"template_id": 3, "name": "Leg Day",  "emoji": "🦵",
     "exercise_names": ["Barbell squat", "Romanian deadlift", "Leg press", "Hip thrust"]},
    {"template_id": 4, "name": "Push Day", "emoji": "🏋️",
     "exercise_names": ["Overhead press", "Lateral raise", "Face pull", "Triceps dip"]},
    {"template_id": 5, "name": "Core Day", "emoji": "🎯",
     "exercise_names": ["Plank", "Ab wheel rollout"]},
]


async def seed_templates(db: AsyncIOMotorDatabase) -> None:
    """Insert default templates only when the collection is empty."""
    if await db.templates.count_documents({"deleted_at": None}) == 0:
        now = datetime.now(timezone.utc)
        await db.templates.insert_many([
            {**t, "last_used_at": None, "deleted_at": None,
             "created_at": now, "user_id": None}
            for t in _TEMPLATE_SEED
        ])
