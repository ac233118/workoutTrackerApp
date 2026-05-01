from pydantic import BaseModel
from typing import Optional


class ExerciseResponse(BaseModel):
    id:            str
    name:          str
    category:      str
    muscle_groups: list[str]
    equipment:     str
    difficulty:    str
    instructions:  Optional[str] = None


class ExerciseListResponse(BaseModel):
    total: int
    skip:  int
    limit: int
    data:  list[ExerciseResponse]
