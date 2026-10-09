from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from backend.services.data_service import (
    PROJECT_DIR,
    get_base_stats,
    get_data_json,
)
from backend.services.update_service import (
    get_last_restore,
    get_last_run_state,
)
from backend.services.about_service import get_about
from backend.services.contacts_service import get_contacts
from backend.services.news_service import get_news, get_news_item
from backend.services.page_service import get_page
from backend.services.media_service import (
    MediaValidationError,
    create_media_category,
    delete_media,
    is_document_name,
    list_media,
    list_media_categories,
    get_media_stats,
    save_document,
    save_image,
    save_video,
    update_media,
)

from backend.search.api import SearchRequest, SearchResponse, execute_search

from backend.services.auth_api import (
    LoginRequest,
    login_admin,
    logout_admin,
    require_admin,
)


app = FastAPI(
    title="Albion API",
    version="1.0.0",
)

from backend.api.admin_base import router as admin_base_router

app.include_router(admin_base_router)

from backend.api.admin_contacts import router as admin_contacts_router

app.include_router(admin_contacts_router)

from backend.api.admin_site_menu import router as admin_site_menu_router

app.include_router(admin_site_menu_router)

from backend.api.admin_settings import (
    router as admin_settings_router,
    public_router as public_settings_router,
)

app.include_router(admin_settings_router)
app.include_router(public_settings_router)

from backend.api.accounts import router as account_router

app.include_router(account_router)

from backend.api.admin_news import router as admin_news_router

app.include_router(admin_news_router)

from backend.api.admin_audit import router as admin_audit_router

app.include_router(admin_audit_router)

from backend.api.admin_about import router as admin_about_router

app.include_router(admin_about_router)

from backend.api.admin_users import router as admin_users_router

app.include_router(admin_users_router)

from backend.api.admin_cabinet_users import router as cabinet_users_router

app.include_router(cabinet_users_router)

from backend.api.tracking import router as tracking_router

app.include_router(tracking_router)

from backend.api.admin_statistics import router as admin_statistics_router

app.include_router(admin_statistics_router)

from backend.api.portfolio import router as portfolio_router

app.include_router(portfolio_router)


from backend.services.site_backup_service import start_scheduler


@app.on_event("startup")
def _start_site_backup_scheduler():
    # Авто-бекап сайта раз в 7 дней (безопасно при нескольких worker'ах —
    # защищено advisory-блокировкой в site_backup_service).
    start_scheduler()


from backend.services.site_menu_service import get_public_menu


@app.get("/api/site-menu")
def site_menu():
    return get_public_menu()

STORAGE_ROOT = PROJECT_DIR / "storage"
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

app.mount("/storage", StaticFiles(directory=STORAGE_ROOT), name="storage")


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Сжатие ответов API.
#
# GET /api/constructions отдаёт ~1.75 МБ JSON без Content-Encoding; gzip
# уменьшает тело примерно в 12 раз (~140 КБ), что критично для мобильных
# сетей. minimum_size=1024 — мелкие ответы не трогаем, чтобы не тратить
# CPU и не менять их Content-Length.
#
# На проде это же обычно делает nginx перед приложением: brotli (сжимает
# лучше gzip) плюс `Cache-Control: immutable` для хешированных файлов
# сборки в /assets/*. Но gzip на самом приложении всё равно нужен: nginx
# может не стоять перед API (dev, внутренние вызовы) либо отдавать /api/*
# без компрессии.
#
# Файлы экспорта портфеля (/api/portfolio/export) — это zip/pdf, то есть
# уже сжатые контейнеры: повторный gzip почти не уменьшает их, лишь тратит
# CPU. Благодаря minimum_size они обычно не пересжимаются; если всё же
# сожмутся — не критично, только небольшая лишняя нагрузка.
#
# Порядок middleware: add_middleware вставляет новый слой наружу, поэтому
# декораторы @app.middleware("http") ниже (no-store для админки, кэш для
# /storage/) окажутся снаружи gzip и продолжат работать как прежде.
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.middleware("http")
async def no_store_admin_responses(request, call_next):
    """Запрещаем браузеру кэшировать ответы админского API.

    Иначе после добавления новых настроек (например, «Оператор карты»)
    браузер может отдавать старый JSON и поле не появится в форме.
    """
    response = await call_next(request)

    if request.url.path.startswith("/api/admin/"):
        response.headers["Cache-Control"] = "no-store"

    return response


@app.middleware("http")
async def cache_storage_assets(request, call_next):
    """Долгий immutable-кэш для статики из /storage/.

    Имена файлов содержат UUID и никогда не переиспользуются, поэтому
    содержимое по конкретному URL неизменяемо. Значит, ответ можно кэшировать
    на год (max-age=31536000) с флагом immutable — браузер не станет даже
    переспрашивать сервер (If-None-Match / If-Modified-Since), что убирает
    повторную загрузку фото и миниатюр при повторных визитах.

    Пути /api/admin/ сюда не попадают, поэтому no-store для админки выше
    не затрагивается.
    """
    response = await call_next(request)

    if request.url.path.startswith("/storage/"):
        response.headers["Cache-Control"] = (
            "public, max-age=31536000, immutable"
        )

    return response


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/constructions")
def constructions(request: Request):
    """Полный список конструкций.

    Отдаём кэшированное сериализованное тело с ETag: повторные заходы
    (карта, список, портфель) не пересобирают 2.8 МБ заново, а браузер
    после max-age присылает If-None-Match и получает 304.
    """
    body, etag = get_data_json()

    headers = {
        "ETag": etag,
        "Cache-Control": "public, max-age=30",
    }

    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)

    return Response(
        content=body,
        media_type="application/json",
        headers=headers,
    )


@app.get("/api/admin/constructions/stats")
def admin_constructions_stats(auth=Depends(require_admin)):
    return {
        "success": True,
        **get_base_stats(),
        "update_state": get_last_run_state(),
        "last_restore": get_last_restore(),
    }



@app.post("/api/search", response_model=SearchResponse)
def search(data: SearchRequest):
    return execute_search(data)


@app.get("/api/contacts")
def contacts():
    return get_contacts()


@app.get("/api/about")
def about():
    return get_about()


@app.get("/api/news")
def news():
    return get_news()


@app.get("/api/news/{slug}")
def news_item(slug: str):
    result = get_news_item(slug)
    if result is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="News not found")
    return result


@app.get("/api/pages/{slug}")
def page(slug: str):
    result = get_page(slug)

    if result is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Page not found")

    return result


@app.post("/api/admin/login")
def admin_login(
    data: LoginRequest,
    request: Request,
):

    return login_admin(
        data,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )


@app.post("/api/admin/media")
async def admin_upload_media(
    file: UploadFile = File(...),
    alt: str | None = Form(default=None),
    original_name: str | None = Form(default=None),
    title: str | None = Form(default=None),
    category_id: list[int] = Form(default=[1]),
    preview_time: float | None = Form(default=None),
    auth=Depends(require_admin),
):

    file_bytes = await file.read()
    resolved_name = original_name or file.filename or "upload"

    try:
        if is_document_name(resolved_name):
            result = save_document(
                file_bytes,
                resolved_name,
                alt=alt,
                title=title,
                category_id=category_id,
            )
        elif file.content_type and file.content_type.startswith("video/"):
            result = save_video(
                file_bytes,
                resolved_name,
                alt=alt,
                title=title,
                category_id=category_id,
                preview_time=preview_time,
            )
        else:
            result = save_image(
                file_bytes,
                resolved_name,
                alt=alt,
                title=title,
                category_id=category_id,
            )
    except MediaValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        "media": result,
    }



@app.post("/api/admin/media/categories")
def admin_create_media_category(
    name: str = Form(...),
    auth=Depends(require_admin),
):

    try:
        category = create_media_category(name)
    except MediaValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        "category": category,
    }


@app.get("/api/admin/media/categories")
def admin_list_media_categories(auth=Depends(require_admin)):
    return {
        "success": True,
        "categories": list_media_categories(),
    }


@app.get("/api/admin/media/stats")
def admin_media_stats(auth=Depends(require_admin)):
    return {
        "success": True,
        **get_media_stats(),
    }


@app.get("/api/admin/media")
def admin_list_media(
    limit: int = 30,
    offset: int = 0,
    category_id: int | None = None,
    auth=Depends(require_admin),
):

    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    media = list_media(
        limit=limit + 1,
        offset=offset,
        category_id=category_id,
    )
    has_more = len(media) > limit

    return {
        "success": True,
        "media": media[:limit],
        "has_more": has_more,
    }


@app.patch("/api/admin/media/{media_id}")
def admin_update_media(
    media_id: int,
    original_name: str | None = Form(default=None),
    category_id: list[int] | None = Form(default=None),
    auth=Depends(require_admin),
):

    try:
        result = update_media(
            media_id,
            original_name=original_name,
            category_id=category_id,
            category_id_provided=category_id is not None,
        )
    except MediaValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        "media": result,
    }




@app.delete("/api/admin/media/{media_id}")
def admin_delete_media(
    media_id: int,
    auth=Depends(require_admin),
):

    try:
        result = delete_media(media_id)
    except MediaValidationError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "success": True,
        "media": result,
    }


@app.get("/api/admin/me")
def admin_me(auth=Depends(require_admin)):
    return {
        "user": auth["user"],
    }


@app.post("/api/admin/logout")
def admin_logout(auth=Depends(require_admin)):
    return logout_admin(auth)

