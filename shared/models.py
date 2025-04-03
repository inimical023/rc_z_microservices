from typing import Dict, Any, Optional, List, Union
from datetime import datetime
from pydantic import BaseModel, Field, field_validator

class CallLogEvent(BaseModel):
    """Call log event"""
    call_id: str
    extension_id: str
    direction: str
    from_number: str
    to_number: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration: Optional[int] = None
    result: str  # "Accepted", "Missed", "Voicemail", etc.
    recording_id: Optional[str] = None
    recording_url: Optional[str] = None
    raw_data: Optional[Dict[str, Any]] = None

class CallLoggedEvent(BaseModel):
    """Event emitted when a call log is retrieved"""
    call_id: str
    extension_id: str
    timestamp: datetime = Field(default_factory=datetime.now)

class LeadOwner(BaseModel):
    """Lead owner"""
    id: str
    name: Optional[str] = None
    email: Optional[str] = None

class Lead(BaseModel):
    """Lead information"""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None
    title: Optional[str] = None
    source: Optional[str] = None
    status: Optional[str] = None
    owner: Optional[LeadOwner] = None
    description: Optional[str] = None
    custom_fields: Optional[Dict[str, Any]] = None

class LeadCreatedEvent(BaseModel):
    """Event emitted when a new lead is created"""
    lead_id: str
    call_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class LeadUpdatedEvent(BaseModel):
    """Event emitted when a lead is updated"""
    lead_id: str
    call_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class Note(BaseModel):
    """Note attached to a lead"""
    title: Optional[str] = None
    content: str
    created_time: datetime = Field(default_factory=datetime.now)

class Attachment(BaseModel):
    """Attachment for a lead"""
    file_name: str
    file_type: str  # MIME type
    content: bytes
    size: int

class RecordingAttachedEvent(BaseModel):
    """Event emitted when a recording is attached to a lead"""
    lead_id: str
    call_id: str
    recording_id: str
    timestamp: datetime = Field(default_factory=datetime.now)

class LeadProcessedEvent(BaseModel):
    """Event emitted when lead processing is complete"""
    lead_id: str
    call_id: Optional[str] = None
    is_new_lead: bool
    has_recording: bool
    notes_added: int
    timestamp: datetime = Field(default_factory=datetime.now)

class CallResult(BaseModel):
    """Result of a call processing operation"""
    call_id: str
    success: bool
    lead_id: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now) 