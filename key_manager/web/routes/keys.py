"""Key management routes: import, list, export, clear."""

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

# Import _app module for patchable names (tests patch key_manager.web._app.*)
import key_manager.web._app as _app_mod
from key_manager.api_models import (
    ImportRequest,
    ImportResponse,
    KeyExportItem,
    KeyExportResponse,
    KeyInfo,
    KeyListResponse,
)
from key_manager.errors import ErrorCode, ErrorResponse, ValidationError
from key_manager.i18n import t
from key_manager.logger import project_logger
from key_manager.parser import mask_key

router = APIRouter(tags=["Keys"])


@router.post("/api/import", response_model=ImportResponse)
async def api_import(body: ImportRequest):
    """Import keys from a JSON file, directory, or inline batch."""
    data = _app_mod._load_keys_data()

    if body.batch:
        # Inline batch import
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        new = 0
        dupes = 0
        errors: list[str] = []
        for raw_key in body.batch:
            if not raw_key or not isinstance(raw_key, str):
                errors.append(f"Invalid key: {raw_key}")
                continue
            key = raw_key.strip()
            if not key:
                errors.append("Empty key in batch")
                continue
            if key in data.get("keys", {}):
                dupes += 1
                continue
            data.setdefault("keys", {})[key] = {
                "key_masked": mask_key(key),
                "provider": "unknown",
                "provider_detected": None,
                "status": "unknown",
                "sources": [{"file": "batch", "batch": "manual", "imported_at": timestamp}],
                "checks": [],
                "tests": {},
                "first_seen": timestamp,
                "last_checked": None,
                "last_tested": None,
                "created_at": timestamp,
            }
            new += 1
        _app_mod._save_keys_data(data)
        project_logger.log_web_action("import", f"batch: {new} new, {dupes} dupes")
        return ImportResponse(new=new, duplicates=dupes, errors=errors)

    allowed_dirs = _app_mod.config.get("scan", {}).get("directories", ["./data/input"])
    if body.file:
        _app_mod.validate_import_path(body.file, allowed_dirs)
    if body.directory:
        _app_mod.validate_import_path(body.directory, allowed_dirs)

    if not body.file and not body.directory:
        body.directory = _app_mod.config["scan"]["directories"][0]

    new, dupes, errors = _app_mod.import_keys(
        file_path=body.file,
        directory=body.directory,
        batch=None,
        keys_file=_app_mod.config["storage"]["keys_file"],
    )
    project_logger.log_web_action("import", f"{body.file or body.directory}: {new} new, {dupes} dupes")
    return ImportResponse(new=new, duplicates=dupes, errors=errors)


@router.post("/api/import/upload")
async def api_import_upload(request: Request):
    """Upload and import a JSON key file."""
    file = None
    filename = ""
    try:
        form = await request.form()
        file = form.get("file")
        if hasattr(file, "filename"):
            filename = file.filename or ""
    except Exception:
        pass

    if not file or not filename:
        response = ErrorResponse.error_factory(
            code=ErrorCode.VALIDATION_FILE_NOT_FOUND,
            message=t("VALIDATION_FILE_NOT_FOUND"),
        )
        return JSONResponse(status_code=400, content=response.model_dump())

    if not filename.endswith(".json"):
        raise ValidationError(
            code=ErrorCode.VALIDATION_FILE_FORMAT,
            message=t("VALIDATION_FILE_FORMAT"),
        )

    content = await file.read()
    try:
        items = json.loads(content)
    except json.JSONDecodeError as e:
        raise ValidationError(
            code=ErrorCode.VALIDATION_FILE_FORMAT,
            message="Uploaded file is not valid JSON",
        ) from e

    if not isinstance(items, list):
        raise ValidationError(
            code=ErrorCode.VALIDATION_FILE_FORMAT,
            message="Uploaded JSON must be an array of key objects",
        )

    keys_file = _app_mod.config["storage"]["keys_file"]
    logs_dir = _app_mod.config["storage"].get("logs_dir", "./data/logs")
    allowed_dirs = [logs_dir, "./data/input"]
    tmp_path = _app_mod.validate_import_path(str(Path(logs_dir).parent / "input" / filename), allowed_dirs)
    tmp_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path.write_bytes(content)

    new, dupes, errors = _app_mod.import_keys(
        file_path=str(tmp_path),
        keys_file=keys_file,
    )

    # Clean up temp file
    try:
        tmp_path.unlink()
    except Exception:
        pass

    project_logger.log_web_action("import_upload", f"{filename}: {new} new, {dupes} dupes")
    return ImportResponse(new=new, duplicates=dupes, errors=errors)


@router.get("/api/keys", response_model=KeyListResponse)
async def api_list_keys(
    provider: str = Query(None, description="Filter by provider"),
    status: str = Query(None, description="Filter by status"),
    batch: str = Query(None, description="Filter by batch label"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=200, description="Items per page"),
    include_full_keys: bool = Query(False, description="Include full keys in response"),
):
    """List keys with optional filters and pagination."""
    data = _app_mod._load_keys_data()
    keys_dict = data.get("keys", {})

    filtered: list[tuple[str, dict]] = []
    for key, info in keys_dict.items():
        if provider and info.get("provider", "").lower() != provider.lower():
            continue
        if status and info.get("status") != status:
            continue
        if batch:
            has_batch = any(s.get("batch") == batch for s in info.get("sources", []))
            if not has_batch:
                continue
        filtered.append((key, info))

    total = len(filtered)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    end = start + page_size
    paged = filtered[start:end]

    key_infos: list[KeyInfo] = []
    for key, info in paged:
        key_infos.append(KeyInfo(
            key=key if include_full_keys else None,
            key_masked=info.get("key_masked", mask_key(key)),
            provider=info.get("provider", "unknown"),
            status=info.get("status", "unknown"),
            last_checked=info.get("last_checked"),
            last_error=info.get("last_error"),
            error_type=info.get("error_type"),
            tests=info.get("tests", {}),
            models=info.get("tests", {}).get("models", []),
            sources_count=len(info.get("sources", [])),
            balance=info.get("balance"),
        ))

    return KeyListResponse(
        keys=key_infos,
        total=total,
        page=page,
        total_pages=total_pages,
        page_size=page_size,
    )


@router.get("/api/keys/export", response_model=KeyExportResponse)
async def api_export_keys(
    provider: str = Query(None, description="Filter by provider"),
):
    """Export all valid keys."""
    data = _app_mod._load_keys_data()
    keys_dict = data.get("keys", {})

    exported: list[KeyExportItem] = []
    for key, info in keys_dict.items():
        if info.get("status") != "valid":
            continue
        if provider and info.get("provider", "").lower() != provider.lower():
            continue
        tests = info.get("tests", {})
        exported.append(KeyExportItem(
            key_masked=info.get("key_masked", mask_key(key)),
            provider=info.get("provider", "unknown"),
            max_tokens=tests.get("max_tokens"),
            max_concurrency=tests.get("max_concurrency"),
        ))

    project_logger.log_web_action("export", f"{len(exported)} keys")
    return KeyExportResponse(keys=exported, total=len(exported))


@router.post("/api/keys/clear")
async def api_clear_keys():
    """Clear all keys from storage."""
    cfg = _app_mod.config
    keys_path = Path(cfg["storage"]["keys_file"])
    cleared = 0
    if keys_path.exists():
        data = _app_mod._load_keys_data()
        cleared = len(data.get("keys", {}))
        data["keys"] = {}
        _app_mod._save_keys_data(data)
    project_logger.log_web_action("clear", f"{cleared} keys removed")
    return {"cleared": cleared}


@router.post("/api/keys/get-full-key")
async def api_get_full_key(request: Request):
    """Get the full key for copying. Expects JSON body with key_masked field."""
    try:
        body = await request.json()
        key_masked = body.get("key_masked", "").strip()
    except Exception:
        raise ValidationError(
            code=ErrorCode.VALIDATION_MISSING_KEY,
            message="key_masked is required",
        )

    if not key_masked:
        raise ValidationError(
            code=ErrorCode.VALIDATION_MISSING_KEY,
            message="key_masked is required",
        )

    data = _app_mod._load_keys_data()
    keys_dict = data.get("keys", {})

    # Find the full key by matching key_masked
    for full_key, info in keys_dict.items():
        if info.get("key_masked") == key_masked:
            project_logger.log_web_action("get_full_key", key_masked)
            return {"key": full_key}

    raise ValidationError(
        code=ErrorCode.VALIDATION_KEY_NOT_FOUND,
        message="Key not found",
    )


@router.post("/api/keys/delete")
async def api_delete_key(request: Request):
    """Delete a single key by key_masked."""
    try:
        body = await request.json()
        key_masked = body.get("key_masked", "").strip()
    except Exception:
        raise ValidationError(
            code=ErrorCode.VALIDATION_MISSING_KEY,
            message="key_masked is required",
        )

    if not key_masked:
        raise ValidationError(
            code=ErrorCode.VALIDATION_MISSING_KEY,
            message="key_masked is required",
        )

    data = _app_mod._load_keys_data()
    keys_dict = data.get("keys", {})

    # Find and delete the key by matching key_masked
    key_to_delete = None
    for full_key, info in keys_dict.items():
        if info.get("key_masked") == key_masked:
            key_to_delete = full_key
            break

    if key_to_delete:
        del keys_dict[key_to_delete]
        _app_mod._save_keys_data(data)
        project_logger.log_web_action("delete", key_masked)
        return {"deleted": 1, "key_masked": key_masked}

    raise ValidationError(
        code=ErrorCode.VALIDATION_KEY_NOT_FOUND,
        message="Key not found",
    )
