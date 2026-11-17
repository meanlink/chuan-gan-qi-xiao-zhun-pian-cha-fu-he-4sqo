from pydantic import BaseModel, Field

class BookingInput(BaseModel):
    request_key: str = Field(min_length=8, max_length=64)
    title: str = Field(min_length=2, max_length=160)
    bath_id: int
    standard_id: int
    start_at: float
    end_at: float
    clean_minutes: int = Field(default=30, ge=0, le=240)
    stabilize_minutes: int = Field(default=20, ge=0, le=240)

class DowntimeInput(BaseModel):
    request_key: str | None = Field(default=None, min_length=8, max_length=64)
    equipment_id: int
    start_at: float
    end_at: float
    reason: str = Field(min_length=2, max_length=200)

class ReadingInput(BaseModel):
    booking_id: int
    bath_id: int
    standard_id: int
    records: list[dict] = Field(min_length=1, max_length=500)
