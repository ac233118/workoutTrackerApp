from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import get_db
from app.schemas.template import CreateTemplateRequest
from app.services import template_service

router = APIRouter(prefix="/templates", tags=["Templates"])


@router.get("", summary="List workout templates")
async def list_templates(
    program:    Optional[str]  = Query(None),
    difficulty: Optional[str]  = Query(None),
    is_public:  Optional[bool] = Query(None),
    created_by: Optional[str]  = Query(None),
    skip:       int            = Query(0,  ge=0),
    limit:      int            = Query(20, ge=1, le=100),
    db: AsyncIOMotorDatabase   = Depends(get_db),
):
    return await template_service.list_templates(
        db,
        program=program,
        difficulty=difficulty,
        is_public=is_public,
        created_by=created_by,
        skip=skip,
        limit=limit,
    )


@router.get("/{template_id}", summary="Get a single template")
async def get_template(
    template_id: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    doc = await template_service.get_template(db, template_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Template not found")
    return doc


@router.post("", status_code=201, summary="Create a workout template")
async def create_template(
    payload: CreateTemplateRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    doc, error = await template_service.create_template(db, payload)
    if error:
        status = 400 if "format" in error else 404
        raise HTTPException(status_code=status, detail=error)
    return doc


@router.post("/{template_id}/start", status_code=201, summary="Start a workout from a template")
async def start_workout(
    template_id: str,
    user_id: str = Query(..., description="The user starting this workout"),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    doc, error = await template_service.start_workout_from_template(db, template_id, user_id)
    if error == "invalid_id":
        raise HTTPException(status_code=400, detail="Invalid template_id format")
    if error == "not_found":
        raise HTTPException(status_code=404, detail="Template not found")
    return doc
