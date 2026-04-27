# Workout Tracker API

FastAPI + MongoDB (Motor async driver) workout tracking backend.

## Setup

```bash
pip install -r requirements.txt
```

Set environment variables (or use defaults):

```bash
export MONGO_URL="mongodb://localhost:27017"
export DB_NAME="workout_tracker"
```

Seed the exercises catalog (run once):

```bash
python seed_exercises.py
```

Start the server:

```bash
uvicorn main:app --reload
```

Interactive docs available at: http://localhost:8000/docs

---

## Endpoints

### GET /exercises
Browse the exercise catalog with optional filters.

```bash
# All exercises
curl "http://localhost:8000/exercises"

# Filter by category
curl "http://localhost:8000/exercises?category=Chest"

# Filter by muscle group
curl "http://localhost:8000/exercises?muscle_group=Glutes"

# Filter by difficulty
curl "http://localhost:8000/exercises?difficulty=Beginner"
```

---

### GET /workouts
List workouts for a user, newest first.

```bash
# All workouts for a user
curl "http://localhost:8000/workouts?user_id=user_abc"

# With pagination
curl "http://localhost:8000/workouts?user_id=user_abc&limit=10&skip=0"

# Filter by exercise category
curl "http://localhost:8000/workouts?user_id=user_abc&category=Legs"
```

---

### GET /workouts/{workout_id}
Fetch a single workout by its MongoDB ObjectId.

```bash
curl "http://localhost:8000/workouts/665f1a2b3c4d5e6f7a8b9c0d"
```

---

### POST /workouts
Create a new workout session. Each exercise entry must reference a valid `exercise_id`
from the exercises collection. The `exercise_name` is stored as a snapshot so historical
records remain accurate if the catalog changes later.

```bash
curl -X POST "http://localhost:8000/workouts" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "user_abc",
    "title": "Push day — Monday",
    "date": "2026-04-11T08:00:00Z",
    "duration_minutes": 55,
    "notes": "Felt strong today, increased bench by 5 kg.",
    "exercises": [
      {
        "exercise_id": "<ObjectId from exercises collection>",
        "exercise_name": "Barbell bench press",
        "order": 1,
        "sets": [
          { "set_number": 1, "reps": 8, "weight_kg": 80, "rest_sec": 90 },
          { "set_number": 2, "reps": 8, "weight_kg": 82.5, "rest_sec": 90 },
          { "set_number": 3, "reps": 6, "weight_kg": 85, "rest_sec": 120 }
        ]
      },
      {
        "exercise_id": "<ObjectId from exercises collection>",
        "exercise_name": "Incline dumbbell press",
        "order": 2,
        "sets": [
          { "set_number": 1, "reps": 10, "weight_kg": 30, "rest_sec": 75 },
          { "set_number": 2, "reps": 10, "weight_kg": 30, "rest_sec": 75 },
          { "set_number": 3, "reps": 8,  "weight_kg": 32.5, "rest_sec": 90 }
        ]
      },
      {
        "exercise_id": "<ObjectId from exercises collection>",
        "exercise_name": "Plank",
        "order": 3,
        "sets": [
          { "set_number": 1, "duration_sec": 60, "rest_sec": 45 },
          { "set_number": 2, "duration_sec": 60, "rest_sec": 45 }
        ]
      }
    ]
  }'
```

---

## Indexes (recommended)

Run once in MongoDB shell or Compass:

```js
db.workouts.createIndex({ user_id: 1, date: -1 })
db.exercises.createIndex({ category: 1 })
db.exercises.createIndex({ muscle_groups: 1 })
```
