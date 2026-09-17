from pydantic import BaseModel


class HealthOut(BaseModel):
    status: str
    app: str
    version: str
    db: str
