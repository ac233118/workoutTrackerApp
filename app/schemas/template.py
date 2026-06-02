from pydantic import BaseModel, Field
from typing import Optional, Literal


# ─── Full-featured template (internal /templates routes) ─────────────────────

class TemplateExerciseIn(BaseModel):
    exercise_id:         str = Field(..., description="_id from the exercises collection")
    exercise_name:       str = Field(..., description="Denormalised name snapshot")
    order:               int = Field(..., ge=1)
    target_sets:         int = Field(..., ge=1)
    target_reps:         Optional[int] = None
    target_duration_sec: Optional[int] = None
    rest_sec:            int = Field(60, ge=0)
    notes:               Optional[str] = None


class CreateTemplateRequest(BaseModel):
    name:                    str
    program:                 Optional[str] = None
    split_day:               Optional[str] = None
    description:             Optional[str] = None
    target_duration_minutes: Optional[int] = None
    difficulty:              Optional[Literal["Beginner", "Intermediate", "Advanced"]] = None
    is_public:               bool = True
    created_by:              Optional[str] = None
    exercises:               list[TemplateExerciseIn] = Field(..., min_length=1)


# ─── Mobile template (/api/templates contract) ────────────────────────────────

class MobileCreateTemplateRequest(BaseModel):
    name:      str
    emoji:     str
    exercises: list[str] = Field(..., min_length=1, max_length=10)


class MobileUpdateTemplateRequest(BaseModel):
    name:      str
    emoji:     str
    exercises: list[str] = Field(..., min_length=1, max_length=10)


class MobileTemplateResponse(BaseModel):
    id:        int
    name:      str
    emoji:     str
    lastDone:  str
    exercises: list[str]
