from fastapi import APIRouter

from app.api.routes import exercises, workouts, templates, mobile_templates, auth

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(exercises.router)
api_router.include_router(workouts.router)
api_router.include_router(templates.router)
api_router.include_router(mobile_templates.router)
