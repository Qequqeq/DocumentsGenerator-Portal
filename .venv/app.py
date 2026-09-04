# -*- coding: utf-8 -*-
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates
from pathlib import Path

app = FastAPI()

TEMPLATES_DIR = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.get("/")
def landing(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})