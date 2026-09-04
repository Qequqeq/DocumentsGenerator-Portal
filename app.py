# -*- coding: utf-8 -*-
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path

app = FastAPI()

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/")
def landing_main(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/auditors")
def landing_auditors(request: Request):
    return templates.TemplateResponse("auditors.html", {"request": request})


@app.get("/organizations")
def landing_organizations(request: Request):
    return templates.TemplateResponse("organizations.html", {"request": request})