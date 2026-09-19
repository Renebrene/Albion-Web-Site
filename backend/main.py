from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.services.data_service import get_data
from backend.services.about_service import get_about
from backend.services.contacts_service import get_contacts


app = FastAPI(
    title="Albion API",
    version="1.0.0",
)

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
