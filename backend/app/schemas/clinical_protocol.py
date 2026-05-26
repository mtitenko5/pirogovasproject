from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional
from app.core.enum.clinical_protocol_status import ClinicalProtocolStatus

class ClinicalProtocolCreate(BaseModel):
    title: str
    version: Optional[str] = None
    content: Optional[str] = None
    file_object_key: Optional[str] = None

class ClinicalProtocolOut(ClinicalProtocolCreate):
    id: int
    status: ClinicalProtocolStatus
    error_message: Optional[str] = None
    uploaded_at: datetime
    updated_at: Optional[datetime] = None
    indexed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)

class ClinicalProtocolListItem(BaseModel):
    id: int
    title: str
    status: ClinicalProtocolStatus
    uploaded_at: datetime

    model_config = ConfigDict(from_attributes=True)
