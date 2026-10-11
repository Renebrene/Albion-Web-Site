from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import PlainTextResponse

from backend.services.auth_api import require_admin
from backend.services.upload_limits import (
    UploadTooLargeError,
    read_upload_limited,
)
from backend.services.import_archive_service import (
    list_archives,
    restore_archive,
)
from backend.services.site_backup_service import (
    create_backup,
    list_backups,
    restore_backup,
)
from backend.services.update_service import (
    get_last_restore,
    get_update_log,
    get_update_log_by_name,
    get_update_status,
    list_update_logs,
    mark_restored,
    mark_site_restored,
    save_uploaded_file,
    start_update,
    stop_update,
)


router = APIRouter(
    prefix="/api/admin/base",
    tags=["admin-base"],
)


@router.get("/archives")
def archives(
    auth=Depends(require_admin),
):
    return {
        "success": True,
        "archives": list_archives(),
    }


@router.get("/restore-info")
def restore_info(
    kind: str = Query("constructions"),
    auth=Depends(require_admin),
):
    """Последнее восстановление из архива для указанной части."""
    try:
        last = get_last_restore(kind)
    except Exception:
        last = None

    return {
        "success": True,
        "kind": kind,
        "last_restore": last,
    }


@router.post("/archives/{import_key}/restore")
def restore(
    import_key: str,
    dry_run: bool = Query(
        False,
        description=(
            "проверить архив и показать план, "
            "не трогая БД и storage"
        ),
    ),
    auth=Depends(require_admin),
):
    try:
        result = restore_archive(
            import_key,
            dry_run=dry_run,
        )

        # Реальное восстановление (не проверка) — сбрасываем ошибку прошлого
        # прогона и показываем дату восстановленной базы конструкций.
        if not dry_run:
            mark_restored(import_key)

        return result
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка восстановления: {exc}",
        ) from exc


# ------------------------------------------------ бекапы сайта


@router.get("/site-backups")
def site_backups(auth=Depends(require_admin)):
    return {
        "success": True,
        "backups": list_backups(),
    }


@router.post("/site-backups")
def site_backup_create(
    reason: str = Query("manual"),
    auth=Depends(require_admin),
):
    """Принудительно создать бекап сайта."""
    try:
        backup = create_backup(reason)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Не удалось создать бекап: {exc}",
        ) from exc

    return {
        "success": True,
        "backup": backup,
        "backups": list_backups(),
    }


@router.post("/site-backups/{name}/restore")
def site_backup_restore(
    name: str,
    dry_run: bool = Query(False),
    auth=Depends(require_admin),
):
    """Восстановить бекап сайта (текущее состояние сохраняется в бекап)."""
    try:
        result = restore_backup(name, dry_run=dry_run)

        if not dry_run:
            mark_site_restored(name)

        return result
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка восстановления: {exc}",
        ) from exc


@router.post("/upload")
async def upload(
    file: UploadFile = File(...),
    auth=Depends(require_admin),
):
    """Загрузка Excel в папку input/ (всегда один файл).

    Предыдущий файл переезжает в .previous и в архив
    после успешного обновления базы.
    """
    try:
        # XLS-выгрузка конструкций: читаем порциями, не более 50 МБ.
        content = read_upload_limited(file, 50 * 1024 * 1024)
    except UploadTooLargeError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc

    try:
        result = save_uploaded_file(
            file.filename or "upload.xlsx",
            content,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка загрузки файла: {exc}",
        ) from exc

    return result


@router.post("/update")
def update(
    dry_run: bool = Query(
        False,
        description=(
            "тестовый прогон: PostgreSQL и archive не меняются"
        ),
    ),
    auth=Depends(require_admin),
):
    """Запускает полное обновление базы (Excel → PostgreSQL)."""
    try:
        return start_update(dry_run=dry_run)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.post("/update/stop")
def update_stop(
    auth=Depends(require_admin),
):
    """Останавливает текущий прогон обновления / dry-run."""
    try:
        return stop_update()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.get("/update/status")
def update_status(
    auth=Depends(require_admin),
):
    """Текущий прогресс обновления для индикаторов."""
    return get_update_status()


@router.get("/update/log", response_class=PlainTextResponse)
def update_log(
    auth=Depends(require_admin),
):
    """Полный текст лога последнего обновления."""
    return get_update_log()


@router.get("/update/logs")
def update_logs(
    auth=Depends(require_admin),
):
    """Список сохранённых логов обновлений."""
    return {
        "success": True,
        "logs": list_update_logs(),
    }


@router.get("/update/logs/{name}", response_class=PlainTextResponse)
def update_log_named(
    name: str,
    auth=Depends(require_admin),
):
    """Содержимое конкретного сохранённого лога."""
    try:
        return get_update_log_by_name(name)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail=str(exc),
        ) from exc