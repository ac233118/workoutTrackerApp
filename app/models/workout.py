from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SetDocument(BaseModel):
    set_number:   int
    reps:         Optional[int]   = None
    weight_kg:    Optional[float] = None
    duration_sec: Optional[int]   = None
    rest_sec:     int = 60


class ExerciseDocument(BaseModel):
    exercise_id:         str
    exercise_name:       str
    order:               int
    sets:                list[SetDocument] = []
    target_sets:         Optional[int]   = None
    target_reps:         Optional[int]   = None
    target_duration_sec: Optional[int]   = None
    rest_sec:            int = 60
    notes:               Optional[str]   = None


class WorkoutDocument(BaseModel):
    user_id:          str
    title:            str
    template_id:      Optional[str]      = None
    date:             datetime
    duration_minutes: Optional[int]      = None
    notes:            Optional[str]      = None
    exercises:        list[ExerciseDocument]
    created_at:       datetime
