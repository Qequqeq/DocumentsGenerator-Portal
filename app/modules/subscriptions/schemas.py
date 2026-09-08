# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from app.shared.timeutils import utcnow


class SubscriptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    plan: str
    started_at: datetime
    expires_at: datetime
    status: str

    @property
    def is_active(self) -> bool:
        return self.status == "active" and self.expires_at > utcnow()


class SubscribeRequest(BaseModel):
    plan: str = Field(..., pattern="^(monthly|yearly)$")