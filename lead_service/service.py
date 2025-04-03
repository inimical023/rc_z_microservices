import asyncio
import logging
import base64
from typing import Dict, Any, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..shared.config import AppConfig, load_config
from ..shared.utils import setup_logging, normalize_phone_number
from ..shared.models import (
    Lead, LeadOwner, Note, Attachment, LeadStatus,
    LeadCreatedEvent, LeadUpdatedEvent, RecordingAttachedEvent
)
from ..shared.message_broker import MessageBroker, create_message_broker

from .zoho_client import ZohoClient

# Models for API requests and responses
class LeadRequest(BaseModel):
    """Request model for creating or updating a lead"""
    phone: str
    firstName: Optional[str] = "Unknown Caller"
    lastName: Optional[str] = "Unknown Caller"
    email: Optional[str] = None
    company: Optional[str] = None
    leadSource: Optional[str] = None
    leadStatus: Optional[str] = None
    ownerId: Optional[str] = None
    description: Optional[str] = None

class LeadResponse(BaseModel):
    """Response model for lead operations"""
    success: bool
    message: str
    leadId: Optional[str] = None

class NoteRequest(BaseModel):
    """Request model for adding a note to a lead"""
    leadId: str
    content: str
    title: Optional[str] = None

class NoteResponse(BaseModel):
    """Response model for note operations"""
    success: bool
    message: str
    noteId: Optional[str] = None

class AttachmentRequest(BaseModel):
    """Request model for attaching a file to a lead"""
    leadId: str
    fileName: str
    contentType: str
    contentBase64: str

class AttachmentResponse(BaseModel):
    """Response model for attachment operations"""
    success: bool
    message: str
    attachmentId: Optional[str] = None

class SearchRequest(BaseModel):
    """Request model for searching leads"""
    phone: str

class SearchResponse(BaseModel):
    """Response model for lead search"""
    success: bool
    message: str
    leads: List[Dict[str, Any]] = []

class LeadOwnerResponse(BaseModel):
    """Response model for lead owner operations"""
    success: bool
    message: str
    owners: List[Dict[str, Any]] = []

class LeadService:
    """Service for handling Zoho CRM leads"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the Lead Service
        
        Args:
            config_path (str, optional): Path to config file. Defaults to None.
        """
        # Load configuration
        self.config = load_config(config_path)
        
        # Set up logging
        self.logger = setup_logging("lead_service", 
                                   log_level=getattr(logging, self.config.services["lead_service"].log_level))
        
        # Initialize Zoho client
        self.zoho_client = ZohoClient(
            client_id=self.config.zoho.client_id,
            client_secret=self.config.zoho.client_secret,
            refresh_token=self.config.zoho.refresh_token,
            base_url=self.config.zoho.base_url,
            logger=self.logger
        )
        
        # Initialize message broker
        self.message_broker = create_message_broker(
            broker_type=self.config.message_broker.type,
            config=self.config.message_broker.dict(),
            logger=self.logger
        )
        
        # Create FastAPI app
        self.app = FastAPI(
            title="RingCentral-Zoho Lead Service",
            description="Service for handling Zoho CRM leads",
            version="1.0.0",
            debug=self.config.services["lead_service"].debug
        )
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Register routes
        self._register_routes()
        
        # Register startup and shutdown events
        self.app.on_event("startup")(self.startup_event)
        self.app.on_event("shutdown")(self.shutdown_event)
    
    def _register_routes(self):
        """Register API routes"""
        
        @self.app.get("/health")
        async def health_check():
            """Health check endpoint"""
            return {"status": "healthy", "service": "lead_service"}
        
        @self.app.post("/api/leads", response_model=LeadResponse)
        async def create_lead(request: LeadRequest):
            """
            Create a new lead in Zoho CRM
            
            Args:
                request (LeadRequest): Lead data
                
            Returns:
                LeadResponse: Response with lead ID
            """
            try:
                # Create lead model
                lead = Lead(
                    phone=request.phone,
                    firstName=request.firstName,
                    lastName=request.lastName,
                    email=request.email,
                    company=request.company,
                    leadSource=request.leadSource,
                    leadStatus=request.leadStatus,
                    description=request.description
                )
                
                # Add owner if provided
                if request.ownerId:
                    lead.owner = LeadOwner(id=request.ownerId)
                
                # Check if lead already exists
                existing_leads = self.zoho_client.search_leads_by_phone(request.phone)
                
                if existing_leads:
                    # Update existing lead
                    lead_id = existing_leads[0]['id']
                    success = self.zoho_client.update_lead(lead_id, lead.dict(exclude_none=True, by_alias=True))
                    
                    if success:
                        # Publish lead updated event
                        await self._publish_lead_updated_event(lead_id, lead)
                        
                        return LeadResponse(
                            success=True,
                            message=f"Lead updated successfully",
                            leadId=lead_id
                        )
                    else:
                        return LeadResponse(
                            success=False,
                            message=f"Failed to update lead",
                            leadId=lead_id
                        )
                else:
                    # Create new lead
                    lead_id = self.zoho_client.create_lead(lead)
                    
                    if lead_id:
                        # Publish lead created event
                        await self._publish_lead_created_event(lead_id, lead)
                        
                        return LeadResponse(
                            success=True,
                            message=f"Lead created successfully",
                            leadId=lead_id
                        )
                    else:
                        return LeadResponse(
                            success=False,
                            message=f"Failed to create lead"
                        )
            except Exception as e:
                self.logger.error(f"Error creating/updating lead: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/leads/search", response_model=SearchResponse)
        async def search_leads(request: SearchRequest):
            """
            Search for leads by phone number
            
            Args:
                request (SearchRequest): Search parameters
                
            Returns:
                SearchResponse: Response with matching leads
            """
            try:
                leads = self.zoho_client.search_leads_by_phone(request.phone)
                
                return SearchResponse(
                    success=True,
                    message=f"Found {len(leads)} leads",
                    leads=leads
                )
            except Exception as e:
                self.logger.error(f"Error searching leads: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/leads/notes", response_model=NoteResponse)
        async def add_note(request: NoteRequest):
            """
            Add a note to a lead
            
            Args:
                request (NoteRequest): Note data
                
            Returns:
                NoteResponse: Response with note ID
            """
            try:
                note_id = self.zoho_client.add_note_to_lead(
                    lead_id=request.leadId,
                    note_content=request.content,
                    title=request.title
                )
                
                if note_id:
                    return NoteResponse(
                        success=True,
                        message=f"Note added successfully",
                        noteId=note_id
                    )
                else:
                    return NoteResponse(
                        success=False,
                        message=f"Failed to add note"
                    )
            except Exception as e:
                self.logger.error(f"Error adding note: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/leads/attachments", response_model=AttachmentResponse)
        async def attach_file(request: AttachmentRequest):
            """
            Attach a file to a lead
            
            Args:
                request (AttachmentRequest): Attachment data
                
            Returns:
                AttachmentResponse: Response with attachment ID
            """
            try:
                # Check if file is already attached
                if self.zoho_client.is_file_already_attached(request.leadId, request.fileName):
                    return AttachmentResponse(
                        success=True,
                        message=f"File {request.fileName} is already attached to lead {request.leadId}",
                        attachmentId="existing"
                    )
                
                # Decode base64 content
                file_content = base64.b64decode(request.contentBase64)
                
                # Attach file
                attachment_id = self.zoho_client.attach_file_to_lead(
                    lead_id=request.leadId,
                    file_name=request.fileName,
                    file_content=file_content,
                    content_type=request.contentType
                )
                
                if attachment_id:
                    # Publish recording attached event
                    await self._publish_recording_attached_event(
                        lead_id=request.leadId,
                        attachment_id=attachment_id,
                        file_name=request.fileName
                    )
                    
                    return AttachmentResponse(
                        success=True,
                        message=f"File attached successfully",
                        attachmentId=attachment_id
                    )
                else:
                    return AttachmentResponse(
                        success=False,
                        message=f"Failed to attach file"
                    )
            except Exception as e:
                self.logger.error(f"Error attaching file: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/lead-owners", response_model=LeadOwnerResponse)
        async def get_lead_owners():
            """
            Get all lead owners from Zoho CRM
            
            Returns:
                LeadOwnerResponse: Response with lead owners
            """
            try:
                users = self.zoho_client.get_users()
                
                # Format users as lead owners
                owners = []
                for user in users:
                    owners.append({
                        "id": user.get("id"),
                        "name": user.get("full_name"),
                        "email": user.get("email"),
                        "role": user.get("role", {}).get("name")
                    })
                
                return LeadOwnerResponse(
                    success=True,
                    message=f"Retrieved {len(owners)} lead owners",
                    owners=owners
                )
            except Exception as e:
                self.logger.error(f"Error retrieving lead owners: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
    
    async def startup_event(self):
        """Startup event handler"""
        self.logger.info("Starting Lead Service")
        await self.message_broker.connect()
    
    async def shutdown_event(self):
        """Shutdown event handler"""
        self.logger.info("Shutting down Lead Service")
        await self.message_broker.disconnect()
    
    async def _publish_lead_created_event(self, lead_id: str, lead: Lead):
        """
        Publish lead created event
        
        Args:
            lead_id (str): Lead ID
            lead (Lead): Lead data
        """
        event = LeadCreatedEvent(
            data={
                "leadId": lead_id,
                "lead": lead.dict(),
                "timestamp": datetime.now().isoformat()
            }
        )
        
        await self.message_broker.publish("lead_created", event)
        self.logger.debug(f"Published lead created event for lead ID {lead_id}")
    
    async def _publish_lead_updated_event(self, lead_id: str, lead: Lead):
        """
        Publish lead updated event
        
        Args:
            lead_id (str): Lead ID
            lead (Lead): Lead data
        """
        event = LeadUpdatedEvent(
            data={
                "leadId": lead_id,
                "lead": lead.dict(),
                "timestamp": datetime.now().isoformat()
            }
        )
        
        await self.message_broker.publish("lead_updated", event)
        self.logger.debug(f"Published lead updated event for lead ID {lead_id}")
    
    async def _publish_recording_attached_event(self, lead_id: str, attachment_id: str, file_name: str):
        """
        Publish recording attached event
        
        Args:
            lead_id (str): Lead ID
            attachment_id (str): Attachment ID
            file_name (str): File name
        """
        event = RecordingAttachedEvent(
            data={
                "leadId": lead_id,
                "attachmentId": attachment_id,
                "fileName": file_name,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        await self.message_broker.publish("recording_attached", event)
        self.logger.debug(f"Published recording attached event for lead ID {lead_id}")

def create_app(config_path: Optional[str] = None) -> FastAPI:
    """
    Create FastAPI application
    
    Args:
        config_path (str, optional): Path to config file. Defaults to None.
        
    Returns:
        FastAPI: FastAPI application
    """
    service = LeadService(config_path)
    return service.app

if __name__ == "__main__":
    import uvicorn
    
    # Load configuration
    config = load_config()
    service_config = config.services["lead_service"]
    
    # Run the application
    uvicorn.run(
        "service:create_app",
        host=service_config.host,
        port=service_config.port,
        reload=service_config.debug
    )