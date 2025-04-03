import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..shared.config import AppConfig, load_config
from ..shared.utils import setup_logging
from ..shared.models import CallLogEvent, CallLoggedEvent, CallResult
from ..shared.message_broker import MessageBroker, create_message_broker

from .ringcentral_client import RingCentralClient

# Models for API requests and responses
class CallLogRequest(BaseModel):
    """Request model for retrieving call logs"""
    extension_ids: List[str]
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    call_direction: str = "Inbound"
    call_result: Optional[str] = None
    hours_back: Optional[int] = None

class CallLogResponse(BaseModel):
    """Response model for call log retrieval"""
    success: bool
    message: str
    call_count: int = 0
    calls: List[Dict[str, Any]] = []

class RecordingRequest(BaseModel):
    """Request model for retrieving a recording"""
    recording_id: str

class RecordingResponse(BaseModel):
    """Response model for recording retrieval"""
    success: bool
    message: str
    content_type: Optional[str] = None
    content_base64: Optional[str] = None

class ExtensionResponse(BaseModel):
    """Response model for extension info"""
    success: bool
    message: str
    extensions: List[Dict[str, Any]] = []

class CallService:
    """Service for handling RingCentral call logs and recordings"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the Call Service
        
        Args:
            config_path (str, optional): Path to config file. Defaults to None.
        """
        # Load configuration
        self.config = load_config(config_path)
        
        # Set up logging
        self.logger = setup_logging("call_service", 
                                   log_level=getattr(logging, self.config.services["call_service"].log_level))
        
        # Initialize RingCentral client
        self.rc_client = RingCentralClient(
            jwt_token=self.config.ringcentral.jwt_token,
            client_id=self.config.ringcentral.client_id,
            client_secret=self.config.ringcentral.client_secret,
            account_id=self.config.ringcentral.account_id,
            base_url=self.config.ringcentral.base_url,
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
            title="RingCentral-Zoho Call Service",
            description="Service for handling RingCentral call logs and recordings",
            version="1.0.0",
            debug=self.config.services["call_service"].debug
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
            return {"status": "healthy", "service": "call_service"}
        
        @self.app.post("/api/call-logs", response_model=CallLogResponse)
        async def get_call_logs(request: CallLogRequest, background_tasks: BackgroundTasks):
            """
            Retrieve call logs from RingCentral and publish to message broker
            
            Args:
                request (CallLogRequest): Request parameters
                background_tasks (BackgroundTasks): Background tasks
                
            Returns:
                CallLogResponse: Response with call logs
            """
            try:
                # Process date range
                start_date, end_date = self._process_date_range(
                    start_date=request.start_date,
                    end_date=request.end_date,
                    hours_back=request.hours_back
                )
                
                # Get call logs in background
                background_tasks.add_task(
                    self._process_call_logs,
                    extension_ids=request.extension_ids,
                    start_date=start_date,
                    end_date=end_date,
                    call_direction=request.call_direction,
                    call_result=request.call_result
                )
                
                return CallLogResponse(
                    success=True,
                    message=f"Call log retrieval started for {len(request.extension_ids)} extensions",
                    call_count=0,
                    calls=[]
                )
                
            except Exception as e:
                self.logger.error(f"Error retrieving call logs: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/recordings", response_model=RecordingResponse)
        async def get_recording(request: RecordingRequest):
            """
            Retrieve a recording from RingCentral
            
            Args:
                request (RecordingRequest): Request parameters
                
            Returns:
                RecordingResponse: Response with recording content
            """
            try:
                content, content_type = self.rc_client.get_recording_content(request.recording_id)
                
                if not content:
                    return RecordingResponse(
                        success=False,
                        message=f"Recording {request.recording_id} not found"
                    )
                
                # Convert content to base64
                content_base64 = base64.b64encode(content).decode('utf-8')
                
                return RecordingResponse(
                    success=True,
                    message=f"Recording {request.recording_id} retrieved successfully",
                    content_type=content_type,
                    content_base64=content_base64
                )
                
            except Exception as e:
                self.logger.error(f"Error retrieving recording: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/extensions", response_model=ExtensionResponse)
        async def get_extensions():
            """
            Get all call queue extensions from RingCentral
            
            Returns:
                ExtensionResponse: Response with extensions
            """
            try:
                call_queues = self.rc_client.get_call_queues()
                
                return ExtensionResponse(
                    success=True,
                    message=f"Retrieved {len(call_queues)} call queues",
                    extensions=call_queues
                )
                
            except Exception as e:
                self.logger.error(f"Error retrieving extensions: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
    
    async def startup_event(self):
        """Startup event handler"""
        self.logger.info("Starting Call Service")
        await self.message_broker.connect()
    
    async def shutdown_event(self):
        """Shutdown event handler"""
        self.logger.info("Shutting down Call Service")
        await self.message_broker.disconnect()
    
    def _process_date_range(self, start_date: Optional[str] = None, 
                           end_date: Optional[str] = None,
                           hours_back: Optional[int] = None) -> tuple:
        """
        Process date range for call log retrieval
        
        Args:
            start_date (str, optional): Start date in ISO format. Defaults to None.
            end_date (str, optional): End date in ISO format. Defaults to None.
            hours_back (int, optional): Hours to look back from current time. Defaults to None.
            
        Returns:
            tuple: (start_date, end_date) in ISO format
        """
        if start_date and end_date:
            return start_date, end_date
        
        if hours_back:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours_back)
            return start_time.isoformat(), end_time.isoformat()
        
        # Default to last 24 hours
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)
        return start_time.isoformat(), end_time.isoformat()
    
    async def _process_call_logs(self, extension_ids: List[str], start_date: str, 
                               end_date: str, call_direction: str = "Inbound",
                               call_result: Optional[str] = None):
        """
        Process call logs from RingCentral and publish to message broker
        
        Args:
            extension_ids (List[str]): List of extension IDs to get call logs for
            start_date (str): Start date in ISO format
            end_date (str): End date in ISO format
            call_direction (str, optional): Call direction filter. Defaults to "Inbound".
            call_result (str, optional): Call result filter. Defaults to None.
        """
        total_calls = 0
        
        for extension_id in extension_ids:
            try:
                # Get call logs for extension
                call_logs = self.rc_client.get_call_logs(
                    extension_id=extension_id,
                    start_date=start_date,
                    end_date=end_date,
                    call_direction=call_direction,
                    call_result=call_result
                )
                
                self.logger.info(f"Retrieved {len(call_logs)} call logs for extension {extension_id}")
                total_calls += len(call_logs)
                
                # Process each call log
                for call_log in call_logs:
                    try:
                        # Parse call log to event
                        call_event = self.rc_client.parse_call_log_to_event(call_log)
                        
                        # Create CallLoggedEvent
                        event = CallLoggedEvent(
                            data={
                                "call": call_event.dict(),
                                "extension_id": extension_id,
                                "processed_time": datetime.now().isoformat()
                            }
                        )
                        
                        # Publish event to message broker
                        await self.message_broker.publish("call_logged", event)
                        self.logger.debug(f"Published call log event for call ID {call_event.id}")
                        
                    except Exception as e:
                        self.logger.error(f"Error processing call log: {str(e)}")
                
            except Exception as e:
                self.logger.error(f"Error retrieving call logs for extension {extension_id}: {str(e)}")
        
        self.logger.info(f"Processed {total_calls} total call logs")

def create_app(config_path: Optional[str] = None) -> FastAPI:
    """
    Create FastAPI application
    
    Args:
        config_path (str, optional): Path to config file. Defaults to None.
        
    Returns:
        FastAPI: FastAPI application
    """
    service = CallService(config_path)
    return service.app

if __name__ == "__main__":
    import uvicorn
    
    # Load configuration
    config = load_config()
    service_config = config.services["call_service"]
    
    # Run the application
    uvicorn.run(
        "service:create_app",
        host=service_config.host,
        port=service_config.port,
        reload=service_config.debug
    )