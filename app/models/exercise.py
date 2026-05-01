from pydantic import BaseModel, Field
from typing import Optional


class ExerciseDocument(BaseModel):
    """Mirrors the shape stored in the exercises collection."""
    name:          str
    category:      str
    muscle_groups: list[str]
    equipment:     str
    difficulty:    str
    instructions:  Optional[str] = None
