import os
import time
from collections import defaultdict, deque

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse
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
from backend.api.chat import router as chat_router

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

from backend.api.admin_home import router as admin_home_router

app.include_router(admin_home_router)

from backend.api.admin_dashboard import router as admin_dashboard_router

app.include_router(admin_dashboard_router)

from backend.api.admin_chat_log import router as admin_chat_log_router

app.include_router(admin_chat_log_router)

app.include_router(chat_router)

from backend.api.info import (
    router as admin_info_router,
    public_router as public_info_router,
)

app.include_router(admin_info_router)
app.include_router(public_info_router)


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


from backend.services.home_service import create_feedback, get_home


@app.get("/api/home")
def home_content():
    """Слайды главной страницы (вертикальные + карточки верхнего слайда).

    Статистика направлений (форматы/конструкции) считается из базы на каждый
    запрос, поэтому кэш браузера/прокси запрещаем — после обновления базы
    конструкций цифры сразу актуальны.
    """
    return JSONResponse(content=get_home(), headers={"Cache-Control": "no-store"})


@app.post("/api/feedback")
def feedback_submit(payload: dict):
    """Форма обратной связи на главной странице."""
    try:
        result = create_feedback(payload or {})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"success": True, **result}

STORAGE_ROOT = PROJECT_DIR / "storage"
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

app.mount("/storage", StaticFiles(directory=STORAGE_ROOT), name="storage")


# CORS: один и тот же origin с фронтенда (через туннель/прокси) в CORS не
# нуждается. Список origin берём из ALBION_ALLOWED_ORIGINS (через запятую);
# без переменной разрешаем только локальную разработку. Wildcard с
# credentials небезопасен и здесь больше не используется.
_allowed_origins_env = os.getenv("ALBION_ALLOWED_ORIGINS", "").strip()

if _allowed_origins_env:
    ALLOWED_ORIGINS = [
        origin.strip()
        for origin in _allowed_origins_env.split(",")
        if origin.strip()
    ]
else:
    ALLOWED_ORIGINS = [
        "http://localhost:9000",
        "http://127.0.0.1:9000",
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Простой in-memory лимит запросов для чувствительных эндпоинтов.
# В пределах одного worker достаточно против простейшего брутфорса на этапе
# разработки/туннеля; на VDS это выносится на nginx/Traefik.
_RATE_RULES = {
    "/api/admin/login": (10, 60),
    "/api/account/login": (10, 60),
    "/api/account/recover": (5, 300),
    "/api/feedback": (20, 60),
}
_rate_buckets: dict[tuple[str, str], deque] = defaultdict(deque)


@app.middleware("http")
async def _rate_limit(request: Request, call_next):
    rule = _RATE_RULES.get(request.url.path)

    if rule:
        limit, window = rule
        ip = request.client.host if request.client else "unknown"
        now = time.monotonic()
        bucket = _rate_buckets[(ip, request.url.path)]

        while bucket and now - bucket[0] > window:
            bucket.popleft()

        if len(bucket) >= limit:
            return JSONResponse(
                status_code=429,
                content={"detail": "Слишком много запросов. Попробуйте позже."},
                headers={"Retry-After": str(window)},
            )

        bucket.append(now)

    return await call_next(request)


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


from backend.services.data_service import get_constructions_stats


@app.get("/api/constructions/stats")
def constructions_stats():
    """Сводка по сети: конструкции / стороны / поверхности / форматы.

    Считается из базы по формуле на каждый запрос (нигде не хранится),
    поэтому после обновления/восстановления базы конструкций значения
    сразу актуальны. Кэш запрещаем.
    """
    return JSONResponse(
        content=get_constructions_stats(),
        headers={"Cache-Control": "no-store"},
    )


@app.get("/api/admin/constructions/stats")
def admin_constructions_stats(auth=Depends(require_admin)):
    return JSONResponse(
        content={
            "success": True,
            **get_base_stats(),
            "update_state": get_last_run_state(),
            "last_restore": get_last_restore(),
        },
        headers={"Cache-Control": "no-store"},
    )



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

