# -*- coding: utf-8 -*-
from fastapi.templating import Jinja2Templates

from app.config import get_settings
from app.shared.timeutils import to_iso_utc

settings = get_settings()

templates = Jinja2Templates(directory=str(settings.templates_dir))
templates.env.filters["iso_utc"] = to_iso_utc