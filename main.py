import gzip
import math
import os
import shutil
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware

import db as _db

PASSWORD = os.environ.get("APP_PASSWORD", "")
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-in-prod")


@asynccontextmanager
async def lifespan(app: FastAPI):
    db_path = Path("imoveis_bauru.db")
    gz_path = Path("imoveis_bauru.db.gz")
    if not db_path.exists() and gz_path.exists():
        print("Descomprimindo banco de dados…", flush=True)
        with gzip.open(gz_path, "rb") as fi, open(db_path, "wb") as fo:
            shutil.copyfileobj(fi, fo)
        print("Banco pronto.", flush=True)
    yield


app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def _authed(r: Request) -> bool:
    return bool(r.session.get("ok"))


@app.get("/")
async def root(r: Request):
    return RedirectResponse("/busca" if _authed(r) else "/login")


@app.get("/login", response_class=HTMLResponse)
async def login_get(r: Request):
    if _authed(r):
        return RedirectResponse("/busca")
    return templates.TemplateResponse("login.html", {"request": r, "error": None})


@app.post("/login")
async def login_post(r: Request, password: str = Form(...)):
    if password == PASSWORD:
        r.session["ok"] = True
        return RedirectResponse("/busca", status_code=303)
    return templates.TemplateResponse(
        "login.html",
        {"request": r, "error": "Senha incorreta."},
        status_code=401,
    )


@app.get("/logout")
async def logout(r: Request):
    r.session.clear()
    return RedirectResponse("/login")


@app.get("/busca", response_class=HTMLResponse)
async def busca(r: Request, q: str = "", page: int = 1):
    if not _authed(r):
        return RedirectResponse("/login")

    q = q.strip()
    page = max(1, page)

    rows, total = _db.search(q, page) if q else ([], 0)
    tp = math.ceil(total / _db.PAGE_SIZE) if total else 0
    page = min(page, tp) if tp else page
    page_range = list(range(max(1, page - 2), min(tp, page + 2) + 1)) if tp > 1 else []

    return templates.TemplateResponse(
        "search.html",
        {
            "request": r,
            "q": q,
            "rows": rows,
            "total": total,
            "page": page,
            "total_pages": tp,
            "page_range": page_range,
        },
    )
