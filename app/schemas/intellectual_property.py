from pydantic import BaseModel


class IntellectualPropertyCreate(BaseModel):
    owner: str
    title: str
    ip_type: str
    registration_number: str
    country: str
    estimated_value: float


class IntellectualPropertyResponse(IntellectualPropertyCreate):
    id: int
    status: str

    class Config:
        from_attributes = True