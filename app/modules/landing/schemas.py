# -*- coding: utf-8 -*-
from pydantic import BaseModel, EmailStr, Field


class SelfHostRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="Имя заявителя")
    contact: str = Field(..., min_length=1, max_length=200, description="Email или телефон")
    comment: str = Field(default="", max_length=2000, description="Комментарий")