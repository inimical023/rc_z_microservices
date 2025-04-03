from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

class CallDirection(str, Enum):
    """Call direction enum"""
    INBOUND = "Inbound"
    OUTBOUND = "Outbound"

class CallResult(str, Enum):
    """Call result enum"""
    COMPLETED = "Completed"
    MISSED = "Missed"
    VOICEMAIL = "Voicemail"
    REJECTED = "Rejected"
    BUSY = "Busy"
    NO_ANSWER = "NoAnswer"

class LeadStatus(str, Enum):
    """Lead status enum"""
    NEW = "New"
    CONTACTED = "Contacted"
    QUALIFIED = "Qualified"
    UNQUALIFIED = "Unqualified"
    MISSED_CALL = "Missed Call"
    ACCEPTED_CALL = "Accepted Call"

class PhoneInfo(BaseModel):
    """Phone number information"""
    phoneNumber: str
    name: Optional[str] = None
    extensionId: Optional[str] = None
    
    @validator('phoneNumber')
    def validate_phone(cls, v):
        """Validate phone number format"""
        if not v:
            raise ValueError('Phone number is required')
        return v

class RecordingInfo(BaseModel):
    """Call recording information"""
    id: str
    contentUri: Optional[str] = None
    duration: Optional[int] = None
    
    @validator('id')
    def validate_id(cls, v):
        """Validate recording ID"""
        if not v:
            raise ValueError('Recording ID is required')
        return v

class CallLogEvent(BaseModel):
    """Call log event model"""
    id: str
    sessionId: Optional[str] = None
    startTime: datetime
    duration: Optional[int] = None
    direction: CallDirection
    result: CallResult
    from_: PhoneInfo = Field(..., alias='from')
    to: PhoneInfo
    recording: Optional[RecordingInfo] = None
    
    class Config:
        allow_population_by_field_name = True
        
    @validator('id')
    def validate_id(cls, v):
        """Validate call ID"""
        if not v:
            raise ValueError('Call ID is required')
        return v

class LeadOwner(BaseModel):
    """Lead owner model"""
    id: str
    name: Optional[str] = None
    email: Optional[str] = None
    
    @validator('id')
    def validate_id(cls, v):
        """Validate owner ID"""
        if not v:
            raise ValueError('Owner ID is required')
        return v

class Lead(BaseModel):
    """Lead model"""
    id: Optional[str] = None
    phone: str
    firstName: Optional[str] = "Unknown Caller"
    lastName: Optional[str] = "Unknown Caller"
    email: Optional[str] = None
    company: Optional[str] = None
    leadSource: Optional[str] = None
    leadStatus: Optional[LeadStatus] = None
    owner: Optional[LeadOwner] = None
    description: Optional[str] = None
    createdTime: Optional[datetime] = None
    modifiedTime: Optional[datetime] = None
    
    @validator('phone')
    def validate_phone(cls, v):
        """Validate phone number"""
        if not v:
            raise ValueError('Phone number is required')
        return v

class Note(BaseModel):
    """Note model"""
    id: Optional[str] = None
    parentId: str
    parentType: str = "Leads"
    title: Optional[str] = None
    content: str
    createdTime: Optional[datetime] = None
    
    @validator('parentId')
    def validate_parent_id(cls, v):
        """Validate parent ID"""
        if not v:
            raise ValueError('Parent ID is required')
        return v
    
    @validator('content')
    def validate_content(cls, v):
        """Validate content"""
        if not v:
            raise ValueError('Content is required')
        return v

class Attachment(BaseModel):
    """Attachment model"""
    id: Optional[str] = None
    parentId: str
    parentType: str = "Leads"
    fileName: str
    fileType: Optional[str] = None
    fileContent: bytes
    
    @validator('parentId')
    def validate_parent_id(cls, v):
        """Validate parent ID"""
        if not v:
            raise ValueError('Parent ID is required')
        return v
    
    @validator('fileName')
    def validate_file_name(cls, v):
        """Validate file name"""
        if not v:
            raise ValueError('File name is required')
        return v
    
    @validator('fileContent')
    def validate_file_content(cls, v):
        """Validate file content"""
        if not v:
            raise ValueError('File content is required')
        return v

class CallProcessingResult(BaseModel):
    """Result of call processing"""
    callId: str
    leadId: Optional[str] = None
    isNewLead: bool = False
    noteId: Optional[str] = None
    attachmentId: Optional[str] = None
    status: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.now)

class EventMessage(BaseModel):
    """Base event message for message broker"""
    eventType: str
    timestamp: datetime = Field(default_factory=datetime.now)
    data: Dict[str, Any]

class CallLoggedEvent(EventMessage):
    """Event emitted when a call log is retrieved"""
    eventType: str = "CallLogged"
    data: Dict[str, Any]

class LeadCreatedEvent(EventMessage):
    """Event emitted when a lead is created"""
    eventType: str = "LeadCreated"
    data: Dict[str, Any]

class LeadUpdatedEvent(EventMessage):
    """Event emitted when a lead is updated"""
    eventType: str = "LeadUpdated"
    data: Dict[str, Any]

class RecordingAttachedEvent(EventMessage):
    """Event emitted when a recording is attached to a lead"""
    eventType: str = "RecordingAttached"
    data: Dict[str, Any]

class LeadProcessedEvent(EventMessage):
    """Event emitted when a lead is fully processed"""
    eventType: str = "LeadProcessed"
    data: Dict[str, Any]