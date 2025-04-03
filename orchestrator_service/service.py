import asyncio
import logging
import json
import base64
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
import httpx

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..shared.config import AppConfig, load_config
from ..shared.utils import setup_logging, normalize_phone_number
from ..shared.models import (
    CallLogEvent, Lead, LeadOwner, LeadStatus, CallResult,
    CallLoggedEvent, LeadCreatedEvent, LeadUpdatedEvent, 
    RecordingAttachedEvent, LeadProcessedEvent
)
from ..shared.message_broker import MessageBroker, create_message_broker

# Models for API requests and responses
class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str
    service: str
    uptime: float
    message_broker_connected: bool
    subscribed_topics: List[str]

class OrchestratorService:
    """Service for orchestrating the workflow between Call Service and Lead Service"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the Orchestrator Service
        
        Args:
            config_path (str, optional): Path to config file. Defaults to None.
        """
        # Load configuration
        self.config = load_config(config_path)
        
        # Set up logging
        self.logger = setup_logging("orchestrator_service", 
                                   log_level=getattr(logging, self.config.services["orchestrator_service"].log_level))
        
        # Initialize message broker
        self.message_broker = create_message_broker(
            broker_type=self.config.message_broker.type,
            config=self.config.message_broker.dict(),
            logger=self.logger
        )
        
        # Initialize HTTP client
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Track subscribed topics
        self.subscribed_topics = []
        
        # Track service start time
        self.start_time = datetime.now()
        
        # Create FastAPI app
        self.app = FastAPI(
            title="RingCentral-Zoho Orchestrator Service",
            description="Service for orchestrating the workflow between Call Service and Lead Service",
            version="1.0.0",
            debug=self.config.services["orchestrator_service"].debug
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
        
        @self.app.get("/health", response_model=HealthResponse)
        async def health_check():
            """Health check endpoint"""
            uptime = (datetime.now() - self.start_time).total_seconds()
            return HealthResponse(
                status="healthy",
                service="orchestrator_service",
                uptime=uptime,
                message_broker_connected=self.message_broker.connected if hasattr(self.message_broker, 'connected') else True,
                subscribed_topics=self.subscribed_topics
            )
    
    async def startup_event(self):
        """Startup event handler"""
        self.logger.info("Starting Orchestrator Service")
        
        # Connect to message broker
        await self.message_broker.connect()
        
        # Subscribe to topics
        await self._subscribe_to_topics()
    
    async def shutdown_event(self):
        """Shutdown event handler"""
        self.logger.info("Shutting down Orchestrator Service")
        
        # Close HTTP client
        await self.http_client.aclose()
        
        # Disconnect from message broker
        await self.message_broker.disconnect()
    
    async def _subscribe_to_topics(self):
        """Subscribe to message broker topics"""
        # Subscribe to call_logged events
        await self.message_broker.subscribe("call_logged", self._handle_call_logged_event)
        self.subscribed_topics.append("call_logged")
        self.logger.info("Subscribed to call_logged events")
        
        # Subscribe to lead_created events
        await self.message_broker.subscribe("lead_created", self._handle_lead_created_event)
        self.subscribed_topics.append("lead_created")
        self.logger.info("Subscribed to lead_created events")
        
        # Subscribe to lead_updated events
        await self.message_broker.subscribe("lead_updated", self._handle_lead_updated_event)
        self.subscribed_topics.append("lead_updated")
        self.logger.info("Subscribed to lead_updated events")
        
        # Subscribe to recording_attached events
        await self.message_broker.subscribe("recording_attached", self._handle_recording_attached_event)
        self.subscribed_topics.append("recording_attached")
        self.logger.info("Subscribed to recording_attached events")
    
    async def _handle_call_logged_event(self, event_data: Dict[str, Any]):
        """
        Handle call logged event
        
        Args:
            event_data (Dict[str, Any]): Event data
        """
        try:
            self.logger.info(f"Received call_logged event")
            
            # Extract call data
            call_data = event_data.get('data', {}).get('call', {})
            extension_id = event_data.get('data', {}).get('extension_id')
            
            if not call_data or not extension_id:
                self.logger.error("Invalid call_logged event: missing call data or extension ID")
                return
            
            # Create CallLogEvent from data
            call = CallLogEvent(**call_data)
            
            # Process call based on result
            if call.result == CallResult.COMPLETED:
                await self._process_accepted_call(call, extension_id)
            elif call.result == CallResult.MISSED:
                await self._process_missed_call(call, extension_id)
            else:
                self.logger.info(f"Ignoring call with result: {call.result}")
        
        except Exception as e:
            self.logger.error(f"Error handling call_logged event: {str(e)}")
    
    async def _handle_lead_created_event(self, event_data: Dict[str, Any]):
        """
        Handle lead created event
        
        Args:
            event_data (Dict[str, Any]): Event data
        """
        try:
            self.logger.info(f"Received lead_created event")
            
            # Extract lead data
            lead_id = event_data.get('data', {}).get('leadId')
            lead_data = event_data.get('data', {}).get('lead', {})
            
            if not lead_id or not lead_data:
                self.logger.error("Invalid lead_created event: missing lead ID or lead data")
                return
            
            # Log lead creation
            self.logger.info(f"Lead created with ID: {lead_id}")
            
            # Check if there's a recording to attach
            # This would be handled by the _process_accepted_call method
            
        except Exception as e:
            self.logger.error(f"Error handling lead_created event: {str(e)}")
    
    async def _handle_lead_updated_event(self, event_data: Dict[str, Any]):
        """
        Handle lead updated event
        
        Args:
            event_data (Dict[str, Any]): Event data
        """
        try:
            self.logger.info(f"Received lead_updated event")
            
            # Extract lead data
            lead_id = event_data.get('data', {}).get('leadId')
            lead_data = event_data.get('data', {}).get('lead', {})
            
            if not lead_id or not lead_data:
                self.logger.error("Invalid lead_updated event: missing lead ID or lead data")
                return
            
            # Log lead update
            self.logger.info(f"Lead updated with ID: {lead_id}")
            
            # Check if there's a recording to attach
            # This would be handled by the _process_accepted_call method
            
        except Exception as e:
            self.logger.error(f"Error handling lead_updated event: {str(e)}")
    
    async def _handle_recording_attached_event(self, event_data: Dict[str, Any]):
        """
        Handle recording attached event
        
        Args:
            event_data (Dict[str, Any]): Event data
        """
        try:
            self.logger.info(f"Received recording_attached event")
            
            # Extract data
            lead_id = event_data.get('data', {}).get('leadId')
            attachment_id = event_data.get('data', {}).get('attachmentId')
            file_name = event_data.get('data', {}).get('fileName')
            
            if not lead_id or not attachment_id or not file_name:
                self.logger.error("Invalid recording_attached event: missing lead ID, attachment ID, or file name")
                return
            
            # Log recording attachment
            self.logger.info(f"Recording {file_name} attached to lead {lead_id} with attachment ID {attachment_id}")
            
            # Publish lead processed event
            await self._publish_lead_processed_event(
                lead_id=lead_id,
                status="completed",
                message=f"Lead processing completed with recording attachment"
            )
            
        except Exception as e:
            self.logger.error(f"Error handling recording_attached event: {str(e)}")
    
    async def _process_accepted_call(self, call: CallLogEvent, extension_id: str):
        """
        Process accepted call
        
        Args:
            call (CallLogEvent): Call log event
            extension_id (str): Extension ID
        """
        try:
            self.logger.info(f"Processing accepted call {call.id}")
            
            # Get phone number from call
            phone_number = call.from_.phoneNumber
            
            if not phone_number:
                self.logger.error(f"Call {call.id} has no phone number")
                return
            
            # Normalize phone number
            normalized_phone = normalize_phone_number(phone_number)
            
            # Search for existing lead
            lead_service_url = f"http://{self.config.services['lead_service'].host}:{self.config.services['lead_service'].port}"
            search_response = await self.http_client.post(
                f"{lead_service_url}/api/leads/search",
                json={"phone": normalized_phone}
            )
            
            search_data = search_response.json()
            existing_leads = search_data.get('leads', [])
            
            # Get lead owner
            lead_owner_id = await self._get_lead_owner_for_extension(extension_id)
            
            # Determine lead status
            lead_status = LeadStatus.ACCEPTED_CALL
            
            if existing_leads:
                # Update existing lead
                lead_id = existing_leads[0]['id']
                self.logger.info(f"Updating existing lead {lead_id} for call {call.id}")
                
                # Create note with call details
                note_content = self._create_call_note_content(call, extension_id)
                
                note_response = await self.http_client.post(
                    f"{lead_service_url}/api/leads/notes",
                    json={
                        "leadId": lead_id,
                        "content": note_content,
                        "title": f"Call on {call.startTime.strftime('%Y-%m-%d %H:%M:%S')}"
                    }
                )
                
                # Check if call has recording
                if call.recording:
                    await self._attach_recording_to_lead(lead_id, call)
            else:
                # Create new lead
                self.logger.info(f"Creating new lead for call {call.id}")
                
                # Create lead data
                lead_data = {
                    "phone": normalized_phone,
                    "firstName": "Unknown Caller",
                    "lastName": "Unknown Caller",
                    "leadSource": f"Extension {extension_id}",
                    "leadStatus": lead_status.value,
                    "ownerId": lead_owner_id,
                    "description": self._create_call_note_content(call, extension_id)
                }
                
                # Create lead
                lead_response = await self.http_client.post(
                    f"{lead_service_url}/api/leads",
                    json=lead_data
                )
                
                lead_result = lead_response.json()
                lead_id = lead_result.get('leadId')
                
                if lead_id and call.recording:
                    await self._attach_recording_to_lead(lead_id, call)
                
                # If no recording, publish lead processed event
                if not call.recording:
                    await self._publish_lead_processed_event(
                        lead_id=lead_id,
                        status="completed",
                        message=f"Lead processing completed without recording"
                    )
        
        except Exception as e:
            self.logger.error(f"Error processing accepted call {call.id}: {str(e)}")
    
    async def _process_missed_call(self, call: CallLogEvent, extension_id: str):
        """
        Process missed call
        
        Args:
            call (CallLogEvent): Call log event
            extension_id (str): Extension ID
        """
        try:
            self.logger.info(f"Processing missed call {call.id}")
            
            # Get phone number from call
            phone_number = call.from_.phoneNumber
            
            if not phone_number:
                self.logger.error(f"Call {call.id} has no phone number")
                return
            
            # Normalize phone number
            normalized_phone = normalize_phone_number(phone_number)
            
            # Search for existing lead
            lead_service_url = f"http://{self.config.services['lead_service'].host}:{self.config.services['lead_service'].port}"
            search_response = await self.http_client.post(
                f"{lead_service_url}/api/leads/search",
                json={"phone": normalized_phone}
            )
            
            search_data = search_response.json()
            existing_leads = search_data.get('leads', [])
            
            # Get lead owner
            lead_owner_id = await self._get_lead_owner_for_extension(extension_id)
            
            # Determine lead status
            lead_status = LeadStatus.MISSED_CALL
            
            if existing_leads:
                # Update existing lead
                lead_id = existing_leads[0]['id']
                self.logger.info(f"Updating existing lead {lead_id} for call {call.id}")
                
                # Create note with call details
                note_content = self._create_call_note_content(call, extension_id)
                
                note_response = await self.http_client.post(
                    f"{lead_service_url}/api/leads/notes",
                    json={
                        "leadId": lead_id,
                        "content": note_content,
                        "title": f"Missed Call on {call.startTime.strftime('%Y-%m-%d %H:%M:%S')}"
                    }
                )
                
                # Publish lead processed event
                await self._publish_lead_processed_event(
                    lead_id=lead_id,
                    status="completed",
                    message=f"Lead processing completed for missed call"
                )
            else:
                # Create new lead
                self.logger.info(f"Creating new lead for call {call.id}")
                
                # Create lead data
                lead_data = {
                    "phone": normalized_phone,
                    "firstName": "Unknown Caller",
                    "lastName": "Unknown Caller",
                    "leadSource": f"Extension {extension_id}",
                    "leadStatus": lead_status.value,
                    "ownerId": lead_owner_id,
                    "description": self._create_call_note_content(call, extension_id)
                }
                
                # Create lead
                lead_response = await self.http_client.post(
                    f"{lead_service_url}/api/leads",
                    json=lead_data
                )
                
                lead_result = lead_response.json()
                lead_id = lead_result.get('leadId')
                
                # Publish lead processed event
                if lead_id:
                    await self._publish_lead_processed_event(
                        lead_id=lead_id,
                        status="completed",
                        message=f"Lead processing completed for missed call"
                    )
        
        except Exception as e:
            self.logger.error(f"Error processing missed call {call.id}: {str(e)}")
    
    async def _attach_recording_to_lead(self, lead_id: str, call: CallLogEvent):
        """
        Attach recording to lead
        
        Args:
            lead_id (str): Lead ID
            call (CallLogEvent): Call log event
        """
        try:
            if not call.recording or not call.recording.id:
                self.logger.warning(f"Call {call.id} has no recording ID")
                return
            
            recording_id = call.recording.id
            self.logger.info(f"Attaching recording {recording_id} to lead {lead_id}")
            
            # Get recording content from Call Service
            call_service_url = f"http://{self.config.services['call_service'].host}:{self.config.services['call_service'].port}"
            recording_response = await self.http_client.post(
                f"{call_service_url}/api/recordings",
                json={"recording_id": recording_id}
            )
            
            recording_data = recording_response.json()
            
            if not recording_data.get('success'):
                self.logger.error(f"Failed to get recording {recording_id}: {recording_data.get('message')}")
                return
            
            content_base64 = recording_data.get('content_base64')
            content_type = recording_data.get('content_type')
            
            if not content_base64 or not content_type:
                self.logger.error(f"Recording {recording_id} has no content or content type")
                return
            
            # Format the call time for the filename
            formatted_call_time = call.startTime.strftime("%Y%m%d_%H%M%S")
            
            # Determine file extension based on content type
            if content_type == "audio/mpeg":
                extension = "mp3"
            elif content_type == "audio/wav":
                extension = "wav"
            else:
                extension = content_type.split('/')[1] if '/' in content_type else "bin"
            
            # Create the filename with the formatted call time
            filename = f"{formatted_call_time}_recording_{recording_id}.{extension}"
            
            # Attach recording to lead
            lead_service_url = f"http://{self.config.services['lead_service'].host}:{self.config.services['lead_service'].port}"
            attachment_response = await self.http_client.post(
                f"{lead_service_url}/api/leads/attachments",
                json={
                    "leadId": lead_id,
                    "fileName": filename,
                    "contentType": content_type,
                    "contentBase64": content_base64
                }
            )
            
            attachment_data = attachment_response.json()
            
            if not attachment_data.get('success'):
                self.logger.error(f"Failed to attach recording to lead {lead_id}: {attachment_data.get('message')}")
            else:
                self.logger.info(f"Successfully attached recording {recording_id} to lead {lead_id}")
        
        except Exception as e:
            self.logger.error(f"Error attaching recording to lead {lead_id}: {str(e)}")
    
    async def _get_lead_owner_for_extension(self, extension_id: str) -> Optional[str]:
        """
        Get lead owner ID for extension
        
        Args:
            extension_id (str): Extension ID
            
        Returns:
            Optional[str]: Lead owner ID
        """
        try:
            # In a real implementation, this would look up the lead owner based on the extension
            # For now, we'll just return the first lead owner from the Lead Service
            
            lead_service_url = f"http://{self.config.services['lead_service'].host}:{self.config.services['lead_service'].port}"
            owners_response = await self.http_client.get(f"{lead_service_url}/api/lead-owners")
            
            owners_data = owners_response.json()
            owners = owners_data.get('owners', [])
            
            if owners:
                # Return the first owner's ID
                return owners[0]['id']
            
            return None
        
        except Exception as e:
            self.logger.error(f"Error getting lead owner for extension {extension_id}: {str(e)}")
            return None
    
    def _create_call_note_content(self, call: CallLogEvent, extension_id: str) -> str:
        """
        Create note content for call
        
        Args:
            call (CallLogEvent): Call log event
            extension_id (str): Extension ID
            
        Returns:
            str: Note content
        """
        # Format call time
        call_time = call.startTime.strftime("%Y-%m-%d %H:%M:%S")
        
        # Create note content
        note_lines = [
            f"Call received on {call_time}",
            "---",
            f"Call ID: {call.id}",
            f"Call direction: {call.direction}",
            f"Call result: {call.result}",
            f"Call duration: {call.duration or 0} seconds",
            f"Caller number: {call.from_.phoneNumber}",
            f"Called extension: {extension_id}",
        ]
        
        if call.recording:
            note_lines.append(f"Recording ID: {call.recording.id}")
        
        return "\n".join(note_lines)
    
    async def _publish_lead_processed_event(self, lead_id: str, status: str, message: str):
        """
        Publish lead processed event
        
        Args:
            lead_id (str): Lead ID
            status (str): Processing status
            message (str): Processing message
        """
        event = LeadProcessedEvent(
            data={
                "leadId": lead_id,
                "status": status,
                "message": message,
                "timestamp": datetime.now().isoformat()
            }
        )
        
        await self.message_broker.publish("lead_processed", event)
        self.logger.debug(f"Published lead processed event for lead ID {lead_id}")

def create_app(config_path: Optional[str] = None) -> FastAPI:
    """
    Create FastAPI application
    
    Args:
        config_path (str, optional): Path to config file. Defaults to None.
        
    Returns:
        FastAPI: FastAPI application
    """
    service = OrchestratorService(config_path)
    return service.app

if __name__ == "__main__":
    import uvicorn
    
    # Load configuration
    config = load_config()
    service_config = config.services["orchestrator_service"]
    
    # Run the application
    uvicorn.run(
        "service:create_app",
        host=service_config.host,
        port=service_config.port,
        reload=service_config.debug
    )