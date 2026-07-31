from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from .models import STAGES


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    token: str


class LeadCreate(BaseModel):
    name: str = ""
    email: str = ""
    phone: str = ""
    company: str = ""
    source: str = "manual"
    stage: str = "new"
    estimated_value: float | None = None
    notes: str = ""


class LeadUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    company: str | None = None
    source: str | None = None
    stage: str | None = None
    estimated_value: float | None = None
    notes: str | None = None


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    body: str
    created_at: datetime


class EmailOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject: str
    sender: str
    received_at: datetime
    raw_body: str
    extraction_json: str
    extraction_method: str
    mailbox: str


class MeetingCreate(BaseModel):
    lead_id: int
    title: str = Field(min_length=1)
    starts_at: datetime
    ends_at: datetime
    location: str = ""
    notes: str = ""


class MeetingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    lead_id: int
    title: str
    starts_at: datetime
    ends_at: datetime
    location: str
    notes: str
    created_at: datetime


class LeadOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str
    phone: str
    company: str
    source: str
    stage: str
    estimated_value: float | None
    notes: str
    created_at: datetime
    updated_at: datetime


class LeadDetail(LeadOut):
    emails: list[EmailOut]
    meetings: list[MeetingOut]
    activities: list[ActivityOut]


class NoteCreate(BaseModel):
    body: str = Field(min_length=1)


class IngestRequest(BaseModel):
    raw_text: str = Field(min_length=1)


class IngestResponse(BaseModel):
    lead: LeadOut
    lead_created: bool
    extraction_method: str


def validate_stage(stage: str) -> str:
    if stage not in STAGES:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail=f"Unknown stage '{stage}'. Valid: {STAGES}")
    return stage
