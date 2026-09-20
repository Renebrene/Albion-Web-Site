from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from backend.services.data_service import PROJECT_DIR, get_data
from backend.services.about_service import get_about
from backend.services.contacts_service import get_contacts
from backend.services.news_service import get_news, get_news_item
from backend.services.page_service import get_page
from backend.services.media_service import MediaValidationError, save_image

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


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/constructions")
def constructions():
    return get_data()


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


ALLOWED_MEDIA_SUBDIRS = {
    "news",
    "about",
    "contacts",
    "employees",
    "constructions",
    "misc",
}


@app.post("/api/admin/media")
async def admin_upload_media(
    file: UploadFile = File(...),
    alt: str | None = Form(default=None),
    title: str | None = Form(default=None),
    storage_subdir: str = Form(default="news"),
    auth=Depends(require_admin),
):
    if storage_subdir not in ALLOWED_MEDIA_SUBDIRS:
        raise HTTPException(
            status_code=400,
            detail="Недопустимый раздел хранения",
        )

    file_bytes = await file.read()

    try:
        result = save_image(
            file_bytes,
            file.filename or "upload",
            alt=alt,
            title=title,
            storage_subdir=storage_subdir,
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


@app.get("/api/admin/me")
def admin_me(auth=Depends(require_admin)):
    return {
        "user": auth["user"],
    }


@app.post("/api/admin/logout")
def admin_logout(auth=Depends(require_admin)):
    return logout_admin(auth)

