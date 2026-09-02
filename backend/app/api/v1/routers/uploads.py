from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile, status

from app.api.deps import CurrentUser, DbSession
from app.core.exceptions import NotFoundError
from app.models.enums import DatasetType
from app.repositories import UploadRepository
from app.schemas.common import Message
from app.schemas.upload import (ColumnMapping, ImportResponse, UploadRead,
                                ValidationResponse)
from app.services.column_mappings import DATASETS
from app.services.excel_service import ExcelService

router = APIRouter(prefix="/uploads", tags=["Data Upload"])


@router.get("/column-mappings", response_model=list[ColumnMapping],
            summary="Accepted columns for every input sheet")
def column_mappings(db: DbSession, user: CurrentUser):
    service = ExcelService(db)
    metric_names = [m.metric_key for m in service.metrics.active()]
    result = []
    for spec in DATASETS:
        required = [f.name for f in spec.fields if f.required]
        optional = [f.name for f in spec.fields if not f.required]
        aliases = {f.name: list(f.all_names) for f in spec.fields}
        if spec.dynamic_metric_columns:
            optional = optional + metric_names
            aliases.update({name: [name] for name in metric_names})
        result.append(ColumnMapping(dataset=spec.dataset, required=required,
                                    optional=optional, aliases=aliases))
    return result


@router.get("", response_model=list[UploadRead], summary="Recent uploads")
def list_uploads(db: DbSession, user: CurrentUser, limit: int = 25):
    return [UploadRead.model_validate(row)
            for row in UploadRepository(db).recent(limit)]


@router.post("/validate", response_model=ValidationResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Upload a file and validate it without importing")
async def validate_file(db: DbSession, user: CurrentUser,
                        file: UploadFile = File(...),
                        dataset: DatasetType | None = Form(default=None)):
    service = ExcelService(db)
    content = await file.read()
    upload = service.store_upload(filename=file.filename or "upload.xlsx",
                                  content=content, content_type=file.content_type,
                                  user_id=user.id)
    return service.validate(upload, dataset)


@router.post("/import", response_model=ImportResponse,
             status_code=status.HTTP_201_CREATED,
             summary="Upload, validate and import a file")
async def import_file(db: DbSession, user: CurrentUser, file: UploadFile = File(...),
                      dataset: DatasetType | None = Form(default=None)):
    service = ExcelService(db)
    content = await file.read()
    upload = service.store_upload(filename=file.filename or "upload.xlsx",
                                  content=content, content_type=file.content_type,
                                  user_id=user.id)
    return service.import_upload(upload, dataset)


@router.post("/{upload_id}/import", response_model=ImportResponse,
             summary="Import a previously validated upload")
def import_existing(upload_id: int, db: DbSession, user: CurrentUser,
                    dataset: DatasetType | None = None):
    upload = UploadRepository(db).get(upload_id)
    if upload is None:
        raise NotFoundError(f"Upload {upload_id} was not found")
    return ExcelService(db).import_upload(upload, dataset)


@router.delete("/{upload_id}", response_model=Message, summary="Delete an upload record")
def delete_upload(upload_id: int, db: DbSession, user: CurrentUser):
    repo = UploadRepository(db)
    upload = repo.get(upload_id)
    if upload is None:
        raise NotFoundError(f"Upload {upload_id} was not found")
    repo.delete(upload)
    return Message(message=f"Upload {upload_id} deleted")
