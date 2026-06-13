import json
from datetime import datetime
from pathlib import Path
from typing import Optional


def load_keys_file(path: str) -> dict:
    keys_path = Path(path)
    if keys_path.exists():
        with open(keys_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "version": "1.0",
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "imports": [],
        "keys": {}
    }


def save_keys_file(data: dict, path: str):
    data["updated_at"] = datetime.utcnow().isoformat() + "Z"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def mask_key(key: str) -> str:
    if len(key) <= 10:
        return key
    return f"{key[:6]}...{key[-4:]}"


def extract_batch_from_filename(filename: str) -> str:
    import re
    match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
    if match:
        return match.group(1)
    return datetime.now().strftime("%Y-%m-%d")


def validate_import_path(path: str, allowed_dirs: list[str]) -> Path:
    """Validate path is within allowed directories. Raises ValidationError if not."""
    from key_manager.errors import ErrorCode, ValidationError
    resolved = Path(path).resolve()
    for allowed in allowed_dirs:
        allowed_resolved = Path(allowed).resolve()
        try:
            resolved.relative_to(allowed_resolved)
            return resolved
        except ValueError:
            continue
    raise ValidationError(
        code=ErrorCode.VALIDATION_FILE_NOT_FOUND,
        message="Path outside allowed directories"
    )


def import_keys(file_path: Optional[str] = None,
                directory: Optional[str] = None,
                batch: Optional[str] = None,
                keys_file: str = "./data/keys.json") -> tuple[int, int, list[str]]:
    errors = []
    new_keys = 0
    duplicates = 0

    data = load_keys_file(keys_file)
    files_to_process = []

    if file_path:
        p = Path(file_path)
        if p.exists() and p.suffix == ".json":
            files_to_process.append(p)
        else:
            errors.append(f"File not found or not JSON: {file_path}")
            return new_keys, duplicates, errors
    elif directory:
        d = Path(directory)
        if d.exists():
            files_to_process.extend(d.glob("*.json"))
        else:
            errors.append(f"Directory not found: {directory}")
            return new_keys, duplicates, errors
    else:
        errors.append("No file or directory specified")
        return new_keys, duplicates, errors

    for fp in files_to_process:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                items = json.load(f)

            if not isinstance(items, list):
                errors.append(f"{fp.name}: not a JSON array")
                continue

            file_batch = batch or extract_batch_from_filename(fp.name)
            import_record = {
                "file": fp.name,
                "batch": file_batch,
                "imported_at": datetime.utcnow().isoformat() + "Z",
                "key_count": len(items),
                "new_keys": 0,
                "duplicates": 0
            }

            for item in items:
                if not isinstance(item, dict) or "key" not in item:
                    continue

                key = item["key"]
                if key in data["keys"]:
                    data["keys"][key]["sources"].append({
                        "file": item.get("file_path", ""),
                        "batch": file_batch,
                        "imported_at": datetime.utcnow().isoformat() + "Z",
                        "original_path": item.get("file_path", ""),
                        "repo": item.get("repo_name", ""),
                        "repo_url": item.get("repo_url", ""),
                        "found_at": item.get("found_at", "")
                    })
                    duplicates += 1
                    import_record["duplicates"] += 1
                else:
                    data["keys"][key] = {
                        "key_masked": mask_key(key),
                        "provider": item.get("provider", "unknown"),
                        "provider_detected": None,
                        "status": "unknown",
                        "sources": [{
                            "file": item.get("file_path", ""),
                            "batch": file_batch,
                            "imported_at": datetime.utcnow().isoformat() + "Z",
                            "original_path": item.get("file_path", ""),
                            "repo": item.get("repo_name", ""),
                            "repo_url": item.get("repo_url", ""),
                            "found_at": item.get("found_at", "")
                        }],
                        "checks": [],
                        "tests": {},
                        "first_seen": datetime.utcnow().isoformat() + "Z",
                        "last_checked": None,
                        "last_tested": None,
                        "created_at": datetime.utcnow().isoformat() + "Z"
                    }
                    new_keys += 1
                    import_record["new_keys"] += 1

            data["imports"].append(import_record)
            save_keys_file(data, keys_file)

        except Exception as e:
            errors.append(f"{fp.name}: {str(e)}")

    return new_keys, duplicates, errors