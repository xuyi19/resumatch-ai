from datetime import datetime

from pydantic import BaseModel, ConfigDict


class HealthOut(BaseModel):
    status: str
    app: str
    version: str
    db: str


class JobOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    title: str
    company: str
    city: str
    salary: str | None = None
    experience: str | None = None
    education: str | None = None
    tags: list[str] = []
    created_at: datetime