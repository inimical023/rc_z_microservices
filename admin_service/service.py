import asyncio
import logging
import json
import httpx
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, EmailStr, validator

from ..shared.config import AppConfig, load_config, create_default_config
from ..shared.utils import setup_logging
from ..shared.models import LeadStatus, CallDirection, CallResult

# Models for API requests and responses
class CredentialsRequest(BaseModel):
    """Request model for updating credentials"""
    rc_jwt: str
    rc_client_id: str
    rc_client_secret: str
    rc_account_id: str = "~"
    zoho_client_id: str
    zoho_client_secret: str
    zoho_refresh_token: str

class CredentialsResponse(BaseModel):
    """Response model for credentials operations"""
    success: bool
    message: str

class ExtensionRequest(BaseModel):
    """Request model for updating extensions"""
    extension_ids: List[str]

class ExtensionResponse(BaseModel):
    """Response model for extension operations"""
    success: bool
    message: str
    extensions: List[Dict[str, Any]] = []

class LeadOwnerRequest(BaseModel):
    """Request model for updating lead owners"""
    owner_ids: List[str]

class LeadOwnerResponse(BaseModel):
    """Response model for lead owner operations"""
    success: bool
    message: str
    owners: List[Dict[str, Any]] = []

class CallLogRequest(BaseModel):
    """Request model for retrieving call logs"""
    extension_ids: List[str]
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    call_direction: str = "Inbound"
    call_result: Optional[str] = None
    hours_back: Optional[int] = None

class CallLogResponse(BaseModel):
    """Response model for call log operations"""
    success: bool
    message: str
    call_count: int = 0

class ServiceStatusResponse(BaseModel):
    """Response model for service status"""
    service: str
    status: str
    uptime: float
    details: Dict[str, Any] = {}

class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str
    service: str
    uptime: float
    services: Dict[str, ServiceStatusResponse] = {}

class AdminService:
    """Service for providing admin interface for RingCentral-Zoho integration"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the Admin Service
        
        Args:
            config_path (str, optional): Path to config file. Defaults to None.
        """
        # Load configuration
        self.config = load_config(config_path)
        
        # Set up logging
        self.logger = setup_logging("admin_service", 
                                   log_level=getattr(logging, self.config.services["admin_service"].log_level))
        
        # Initialize HTTP client
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Track service start time
        self.start_time = datetime.now()
        
        # Create FastAPI app
        self.app = FastAPI(
            title="RingCentral-Zoho Admin Service",
            description="Admin interface for RingCentral-Zoho integration",
            version="1.0.0",
            debug=self.config.services["admin_service"].debug
        )
        
        # Add CORS middleware
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        
        # Set up templates
        self.templates = Jinja2Templates(directory="templates")
        
        # Mount static files
        self.app.mount("/static", StaticFiles(directory="static"), name="static")
        
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
            
            # Check status of all services
            services = {}
            for service_name, service_config in self.config.services.items():
                if service_name != "admin_service":
                    service_status = await self._check_service_health(service_name, service_config)
                    services[service_name] = service_status
            
            return HealthResponse(
                status="healthy",
                service="admin_service",
                uptime=uptime,
                services=services
            )
        
        @self.app.get("/", response_class=HTMLResponse)
        async def index(request: Request):
            """Admin dashboard"""
            return self.templates.TemplateResponse(
                "index.html",
                {"request": request, "title": "RingCentral-Zoho Admin"}
            )
        
        @self.app.get("/api/services", response_model=Dict[str, ServiceStatusResponse])
        async def get_services():
            """Get status of all services"""
            services = {}
            for service_name, service_config in self.config.services.items():
                if service_name != "admin_service":
                    service_status = await self._check_service_health(service_name, service_config)
                    services[service_name] = service_status
            
            return services
        
        @self.app.post("/api/credentials", response_model=CredentialsResponse)
        async def update_credentials(request: CredentialsRequest):
            """
            Update RingCentral and Zoho credentials
            
            Args:
                request (CredentialsRequest): Credentials data
                
            Returns:
                CredentialsResponse: Response with status
            """
            try:
                # Update configuration
                self.config.ringcentral.jwt_token = request.rc_jwt
                self.config.ringcentral.client_id = request.rc_client_id
                self.config.ringcentral.client_secret = request.rc_client_secret
                self.config.ringcentral.account_id = request.rc_account_id
                
                self.config.zoho.client_id = request.zoho_client_id
                self.config.zoho.client_secret = request.zoho_client_secret
                self.config.zoho.refresh_token = request.zoho_refresh_token
                
                # Save configuration to file
                with open("config.json", "w") as f:
                    json.dump(self.config.dict(), f, indent=2)
                
                return CredentialsResponse(
                    success=True,
                    message="Credentials updated successfully"
                )
            except Exception as e:
                self.logger.error(f"Error updating credentials: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/extensions", response_model=ExtensionResponse)
        async def get_extensions():
            """
            Get all call queue extensions from RingCentral
            
            Returns:
                ExtensionResponse: Response with extensions
            """
            try:
                # Get extensions from Call Service
                call_service_url = f"http://{self.config.services['call_service'].host}:{self.config.services['call_service'].port}"
                response = await self.http_client.get(f"{call_service_url}/api/extensions")
                
                if response.status_code != 200:
                    return ExtensionResponse(
                        success=False,
                        message=f"Failed to get extensions: {response.text}"
                    )
                
                data = response.json()
                
                return ExtensionResponse(
                    success=True,
                    message=f"Retrieved {len(data.get('extensions', []))} extensions",
                    extensions=data.get('extensions', [])
                )
            except Exception as e:
                self.logger.error(f"Error getting extensions: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/extensions", response_model=ExtensionResponse)
        async def update_extensions(request: ExtensionRequest):
            """
            Update extensions to monitor
            
            Args:
                request (ExtensionRequest): Extension data
                
            Returns:
                ExtensionResponse: Response with status
            """
            try:
                # Save extensions to configuration
                # In a real implementation, this would be stored in a database
                # For now, we'll just log it
                self.logger.info(f"Updated extensions: {request.extension_ids}")
                
                return ExtensionResponse(
                    success=True,
                    message=f"Updated {len(request.extension_ids)} extensions",
                    extensions=[{"id": ext_id} for ext_id in request.extension_ids]
                )
            except Exception as e:
                self.logger.error(f"Error updating extensions: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/lead-owners", response_model=LeadOwnerResponse)
        async def get_lead_owners():
            """
            Get all lead owners from Zoho CRM
            
            Returns:
                LeadOwnerResponse: Response with lead owners
            """
            try:
                # Get lead owners from Lead Service
                lead_service_url = f"http://{self.config.services['lead_service'].host}:{self.config.services['lead_service'].port}"
                response = await self.http_client.get(f"{lead_service_url}/api/lead-owners")
                
                if response.status_code != 200:
                    return LeadOwnerResponse(
                        success=False,
                        message=f"Failed to get lead owners: {response.text}"
                    )
                
                data = response.json()
                
                return LeadOwnerResponse(
                    success=True,
                    message=f"Retrieved {len(data.get('owners', []))} lead owners",
                    owners=data.get('owners', [])
                )
            except Exception as e:
                self.logger.error(f"Error getting lead owners: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/lead-owners", response_model=LeadOwnerResponse)
        async def update_lead_owners(request: LeadOwnerRequest):
            """
            Update lead owners
            
            Args:
                request (LeadOwnerRequest): Lead owner data
                
            Returns:
                LeadOwnerResponse: Response with status
            """
            try:
                # Save lead owners to configuration
                # In a real implementation, this would be stored in a database
                # For now, we'll just log it
                self.logger.info(f"Updated lead owners: {request.owner_ids}")
                
                return LeadOwnerResponse(
                    success=True,
                    message=f"Updated {len(request.owner_ids)} lead owners",
                    owners=[{"id": owner_id} for owner_id in request.owner_ids]
                )
            except Exception as e:
                self.logger.error(f"Error updating lead owners: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/process-calls", response_model=CallLogResponse)
        async def process_calls(request: CallLogRequest):
            """
            Process call logs
            
            Args:
                request (CallLogRequest): Call log request
                
            Returns:
                CallLogResponse: Response with status
            """
            try:
                # Process call logs using Call Service
                call_service_url = f"http://{self.config.services['call_service'].host}:{self.config.services['call_service'].port}"
                response = await self.http_client.post(
                    f"{call_service_url}/api/call-logs",
                    json=request.dict()
                )
                
                if response.status_code != 200:
                    return CallLogResponse(
                        success=False,
                        message=f"Failed to process call logs: {response.text}"
                    )
                
                data = response.json()
                
                return CallLogResponse(
                    success=True,
                    message=data.get('message', "Call log processing started"),
                    call_count=data.get('call_count', 0)
                )
            except Exception as e:
                self.logger.error(f"Error processing call logs: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/config", response_model=Dict[str, Any])
        async def get_config():
            """
            Get current configuration
            
            Returns:
                Dict[str, Any]: Current configuration
            """
            # Return a sanitized version of the configuration
            # (without sensitive information like tokens and passwords)
            sanitized_config = {
                "services": {
                    name: {
                        "host": service.host,
                        "port": service.port,
                        "log_level": service.log_level,
                        "debug": service.debug
                    } for name, service in self.config.services.items()
                },
                "message_broker": {
                    "type": self.config.message_broker.type
                }
            }
            
            return sanitized_config
        
        @self.app.post("/api/config", response_model=Dict[str, Any])
        async def update_config(config: Dict[str, Any]):
            """
            Update configuration
            
            Args:
                config (Dict[str, Any]): New configuration
                
            Returns:
                Dict[str, Any]: Updated configuration
            """
            try:
                # Update configuration
                # In a real implementation, this would update the configuration file
                # For now, we'll just log it
                self.logger.info(f"Updated configuration: {config}")
                
                return config
            except Exception as e:
                self.logger.error(f"Error updating configuration: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/create-default-config")
        async def create_default_config_endpoint():
            """
            Create default configuration file
            
            Returns:
                Dict[str, Any]: Default configuration
            """
            try:
                create_default_config("config.json")
                
                # Reload configuration
                self.config = load_config("config.json")
                
                return {"message": "Default configuration created successfully"}
            except Exception as e:
                self.logger.error(f"Error creating default configuration: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
    
    async def startup_event(self):
        """Startup event handler"""
        self.logger.info("Starting Admin Service")
    
    async def shutdown_event(self):
        """Shutdown event handler"""
        self.logger.info("Shutting down Admin Service")
        
        # Close HTTP client
        await self.http_client.aclose()
    
    async def _check_service_health(self, service_name: str, service_config: Any) -> ServiceStatusResponse:
        """
        Check health of a service
        
        Args:
            service_name (str): Service name
            service_config (Any): Service configuration
            
        Returns:
            ServiceStatusResponse: Service status
        """
        try:
            service_url = f"http://{service_config.host}:{service_config.port}"
            response = await self.http_client.get(f"{service_url}/health", timeout=2.0)
            
            if response.status_code == 200:
                data = response.json()
                return ServiceStatusResponse(
                    service=service_name,
                    status="healthy",
                    uptime=data.get('uptime', 0),
                    details=data
                )
            else:
                return ServiceStatusResponse(
                    service=service_name,
                    status="unhealthy",
                    uptime=0,
                    details={"error": f"HTTP {response.status_code}: {response.text}"}
                )
        except Exception as e:
            return ServiceStatusResponse(
                service=service_name,
                status="unreachable",
                uptime=0,
                details={"error": str(e)}
            )

def create_app(config_path: Optional[str] = None) -> FastAPI:
    """
    Create FastAPI application
    
    Args:
        config_path (str, optional): Path to config file. Defaults to None.
        
    Returns:
        FastAPI: FastAPI application
    """
    service = AdminService(config_path)
    return service.app

if __name__ == "__main__":
    import uvicorn
    
    # Load configuration
    config = load_config()
    service_config = config.services["admin_service"]
    
    # Run the application
    uvicorn.run(
        "service:create_app",
        host=service_config.host,
        port=service_config.port,
        reload=service_config.debug
    )