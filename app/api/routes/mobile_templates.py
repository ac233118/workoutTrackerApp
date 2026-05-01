from fastapi import APIRouter, Depends, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.db.mongo import get_db
from app.schemas.template import MobileCreateTemplateRequest
from app.services import template_service

router = APIRouter(prefix="/api/templates", tags=["Mobile Templates"])


@router.get("", status_code=200, summary="List templates (mobile contract)")
async def list_templates(db: AsyncIOMotorDatabase = Depends(get_db)):
    """Returns a bare JSON array — exact shape the mobile app expects."""
    return await template_service.mobile_list_templates(db)


@router.post("", status_code=201, summary="Create a template (mobile contract)")
async def create_template(
    payload: MobileCreateTemplateRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    return await template_service.mobile_create_template(db, payload)


@router.put("/{template_id}/used", status_code=200, summary="Mark template as used")
async def mark_used(
    template_id: int,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    found = await template_service.mobile_mark_used(db, template_id)
    if not found:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"success": True}


@router.delete("/{template_id}", status_code=200, summary="Soft-delete a template")
async def delete_template(
    template_id: int,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    found = await template_service.mobile_delete_template(db, template_id)
    if not found:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"success": True}
