from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SetIn(BaseModel):
    set_number:   int
    reps:         Optional[int]   = None
    weight_kg:    Optional[float] = None
    duration_sec: Optional[int]   = None
    rest_sec:     int = 60


class ExerciseIn(BaseModel):
    exercise_id:   str = Field(..., description="_id from the exercises collection")
    exercise_name: str = Field(..., description="Denormalised name snapshot")
    order:         int = Field(..., ge=1)
    sets:          list[SetIn] = Field(..., min_length=1)


class CreateWorkoutRequest(BaseModel):
    user_id:          str
    title:            str
    date:             Optional[datetime] = None
    duration_minutes: Optional[int]      = None
    notes:            Optional[str]      = None
    exercises:        list[ExerciseIn]   = Field(..., min_length=1)
