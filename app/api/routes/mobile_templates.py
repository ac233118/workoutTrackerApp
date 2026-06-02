from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import get_db
from app.core.dependencies import get_current_user, get_optional_user
from app.schemas.template import MobileCreateTemplateRequest, MobileUpdateTemplateRequest
from app.services import template_service

router = APIRouter(prefix="/api/templates", tags=["Mobile Templates"])


@router.get("", status_code=200, summary="List templates (mobile contract)")
async def list_templates(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: Optional[dict] = Depends(get_optional_user),
):
    """Returns templates belonging to the user + system templates (user_id=None)."""
    user_id = str(current_user["_id"]) if current_user else None
    return await template_service.mobile_list_templates(db, user_id=user_id)


@router.post("", status_code=201, summary="Create a template (mobile contract)")
async def create_template(
    payload: MobileCreateTemplateRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user["_id"])
    return await template_service.mobile_create_template(db, payload, user_id=user_id)


@router.put("/{template_id}", status_code=200, summary="Update a custom template")
async def update_template(
    template_id: int,
    payload: MobileUpdateTemplateRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user["_id"])
    updated = await template_service.mobile_update_template(
        db,
        template_id=template_id,
        user_id=user_id,
        name=payload.name,
        emoji=payload.emoji,
        exercises=payload.exercises,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Template not found or not yours to edit")
    return updated


@router.put("/{template_id}/used", status_code=200, summary="Mark template as used")
async def mark_used(
    template_id: int,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    found = await template_service.mobile_mark_used(db, template_id)
    if not found:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"success": True}


@router.delete("/{template_id}", status_code=200, summary="Delete a custom template")
async def delete_template(
    template_id: int,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    user_id = str(current_user["_id"])
    found = await template_service.mobile_delete_template(
        db, template_id=template_id, user_id=user_id
    )
    if not found:
        raise HTTPException(
            status_code=404,
            detail="Template not found or not yours to delete",
        )
    return {"success": True}
