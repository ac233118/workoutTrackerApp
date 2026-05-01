from pydantic import BaseModel
from typing import Optional, Literal
from datetime import datetime


class TemplateExerciseDocument(BaseModel):
    exercise_id:         str
    exercise_name:       str
    order:               int
    target_sets:         int
    target_reps:         Optional[int] = None
    target_duration_sec: Optional[int] = None
    rest_sec:            int = 60
    notes:               Optional[str] = None


class TemplateDocument(BaseModel):
    """Full-featured template stored in the templates collection."""
    name:                    str
    program:                 Optional[str]      = None
    split_day:               Optional[str]      = None
    description:             Optional[str]      = None
    target_duration_minutes: Optional[int]      = None
    difficulty:              Optional[Literal["Beginner", "Intermediate", "Advanced"]] = None
    is_public:               bool               = True
    created_by:              Optional[str]      = None
    exercises:               list[TemplateExerciseDocument]
    created_at:              datetime


class MobileTemplateDocument(BaseModel):
    """Lightweight template used by the mobile /api/templates contract."""
    template_id:    int
    name:           str
    emoji:          str
    exercise_names: list[str]
    last_used_at:   Optional[datetime] = None
    deleted_at:     Optional[datetime] = None
    created_at:     datetime
    user_id:        Optional[str]      = None
