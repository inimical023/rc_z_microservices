import asyncio
import logging
import json
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, validator

from ..shared.config import AppConfig, load_config
from ..shared.utils import setup_logging
from ..shared.models import LeadProcessedEvent
from ..shared.message_broker import MessageBroker, create_message_broker

# Models for API requests and responses
class EmailConfig(BaseModel):
    """Email configuration model"""
    smtp_server: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    use_tls: bool = True
    from_email: EmailStr
    
    @validator('smtp_port')
    def validate_port(cls, v):
        """Validate SMTP port"""
        if v < 1 or v > 65535:
            raise ValueError("SMTP port must be between 1 and 65535")
        return v

class EmailTemplate(BaseModel):
    """Email template model"""
    subject: str
    body_html: str
    body_text: str

class EmailRecipient(BaseModel):
    """Email recipient model"""
    email: EmailStr
    name: Optional[str] = None

class EmailRequest(BaseModel):
    """Request model for sending an email"""
    recipients: List[EmailRecipient]
    subject: str
    body_html: Optional[str] = None
    body_text: Optional[str] = None
    cc: List[EmailRecipient] = []
    bcc: List[EmailRecipient] = []

class EmailResponse(BaseModel):
    """Response model for email operations"""
    success: bool
    message: str

class NotificationConfig(BaseModel):
    """Notification configuration model"""
    enabled: bool = True
    recipients: List[EmailRecipient] = []
    cc: List[EmailRecipient] = []
    bcc: List[EmailRecipient] = []
    templates: Dict[str, EmailTemplate] = {}

class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str
    service: str
    uptime: float
    message_broker_connected: bool
    subscribed_topics: List[str]
    notifications_enabled: bool

class NotificationService:
    """Service for sending notifications"""
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the Notification Service
        
        Args:
            config_path (str, optional): Path to config file. Defaults to None.
        """
        # Load configuration
        self.config = load_config(config_path)
        
        # Set up logging
        self.logger = setup_logging("notification_service", 
                                   log_level=getattr(logging, self.config.services["notification_service"].log_level))
        
        # Initialize message broker
        self.message_broker = create_message_broker(
            broker_type=self.config.message_broker.type,
            config=self.config.message_broker.dict(),
            logger=self.logger
        )
        
        # Track subscribed topics
        self.subscribed_topics = []
        
        # Track service start time
        self.start_time = datetime.now()
        
        # Load notification configuration
        self.notification_config = self._load_notification_config()
        
        # Create FastAPI app
        self.app = FastAPI(
            title="RingCentral-Zoho Notification Service",
            description="Service for sending notifications",
            version="1.0.0",
            debug=self.config.services["notification_service"].debug
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
                service="notification_service",
                uptime=uptime,
                message_broker_connected=self.message_broker.connected if hasattr(self.message_broker, 'connected') else True,
                subscribed_topics=self.subscribed_topics,
                notifications_enabled=self.notification_config.enabled
            )
        
        @self.app.post("/api/email", response_model=EmailResponse)
        async def send_email(request: EmailRequest, background_tasks: BackgroundTasks):
            """
            Send an email
            
            Args:
                request (EmailRequest): Email request
                background_tasks (BackgroundTasks): Background tasks
                
            Returns:
                EmailResponse: Response with status
            """
            try:
                if not self.notification_config.enabled:
                    return EmailResponse(
                        success=False,
                        message="Notifications are disabled"
                    )
                
                # Send email in background
                background_tasks.add_task(
                    self._send_email,
                    recipients=request.recipients,
                    subject=request.subject,
                    body_html=request.body_html,
                    body_text=request.body_text,
                    cc=request.cc,
                    bcc=request.bcc
                )
                
                return EmailResponse(
                    success=True,
                    message="Email sending started"
                )
            except Exception as e:
                self.logger.error(f"Error sending email: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.post("/api/config", response_model=NotificationConfig)
        async def update_config(config: NotificationConfig):
            """
            Update notification configuration
            
            Args:
                config (NotificationConfig): New configuration
                
            Returns:
                NotificationConfig: Updated configuration
            """
            try:
                self.notification_config = config
                self.logger.info("Notification configuration updated")
                return self.notification_config
            except Exception as e:
                self.logger.error(f"Error updating notification configuration: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.app.get("/api/config", response_model=NotificationConfig)
        async def get_config():
            """
            Get notification configuration
            
            Returns:
                NotificationConfig: Current configuration
            """
            return self.notification_config
    
    async def startup_event(self):
        """Startup event handler"""
        self.logger.info("Starting Notification Service")
        
        # Connect to message broker
        await self.message_broker.connect()
        
        # Subscribe to topics
        await self._subscribe_to_topics()
    
    async def shutdown_event(self):
        """Shutdown event handler"""
        self.logger.info("Shutting down Notification Service")
        
        # Disconnect from message broker
        await self.message_broker.disconnect()
    
    async def _subscribe_to_topics(self):
        """Subscribe to message broker topics"""
        # Subscribe to lead_processed events
        await self.message_broker.subscribe("lead_processed", self._handle_lead_processed_event)
        self.subscribed_topics.append("lead_processed")
        self.logger.info("Subscribed to lead_processed events")
    
    async def _handle_lead_processed_event(self, event_data: Dict[str, Any]):
        """
        Handle lead processed event
        
        Args:
            event_data (Dict[str, Any]): Event data
        """
        try:
            self.logger.info(f"Received lead_processed event")
            
            # Extract data
            lead_id = event_data.get('data', {}).get('leadId')
            status = event_data.get('data', {}).get('status')
            message = event_data.get('data', {}).get('message')
            timestamp = event_data.get('data', {}).get('timestamp')
            
            if not lead_id or not status:
                self.logger.error("Invalid lead_processed event: missing lead ID or status")
                return
            
            # Log lead processing
            self.logger.info(f"Lead {lead_id} processed with status {status}: {message}")
            
            # Send notification if enabled
            if self.notification_config.enabled and self.notification_config.recipients:
                # Get template
                template = self.notification_config.templates.get(status, self._get_default_template(status))
                
                # Format subject and body
                subject = template.subject.format(lead_id=lead_id, status=status)
                body_html = template.body_html.format(
                    lead_id=lead_id,
                    status=status,
                    message=message,
                    timestamp=timestamp
                )
                body_text = template.body_text.format(
                    lead_id=lead_id,
                    status=status,
                    message=message,
                    timestamp=timestamp
                )
                
                # Send email
                await self._send_email(
                    recipients=self.notification_config.recipients,
                    subject=subject,
                    body_html=body_html,
                    body_text=body_text,
                    cc=self.notification_config.cc,
                    bcc=self.notification_config.bcc
                )
        
        except Exception as e:
            self.logger.error(f"Error handling lead_processed event: {str(e)}")
    
    def _load_notification_config(self) -> NotificationConfig:
        """
        Load notification configuration
        
        Returns:
            NotificationConfig: Notification configuration
        """
        # Create default templates
        templates = {
            "completed": EmailTemplate(
                subject="Lead {lead_id} Processing Completed",
                body_html="""
                <html>
                <body>
                    <h1>Lead Processing Completed</h1>
                    <p>Lead ID: {lead_id}</p>
                    <p>Status: {status}</p>
                    <p>Message: {message}</p>
                    <p>Timestamp: {timestamp}</p>
                </body>
                </html>
                """,
                body_text="""
                Lead Processing Completed
                
                Lead ID: {lead_id}
                Status: {status}
                Message: {message}
                Timestamp: {timestamp}
                """
            ),
            "error": EmailTemplate(
                subject="Lead {lead_id} Processing Error",
                body_html="""
                <html>
                <body>
                    <h1>Lead Processing Error</h1>
                    <p>Lead ID: {lead_id}</p>
                    <p>Status: {status}</p>
                    <p>Error: {message}</p>
                    <p>Timestamp: {timestamp}</p>
                </body>
                </html>
                """,
                body_text="""
                Lead Processing Error
                
                Lead ID: {lead_id}
                Status: {status}
                Error: {message}
                Timestamp: {timestamp}
                """
            )
        }
        
        # Create default configuration
        return NotificationConfig(
            enabled=True,
            recipients=[],
            templates=templates
        )
    
    def _get_default_template(self, status: str) -> EmailTemplate:
        """
        Get default template for status
        
        Args:
            status (str): Status
            
        Returns:
            EmailTemplate: Email template
        """
        if status == "error":
            return EmailTemplate(
                subject="Lead {lead_id} Processing Error",
                body_html="""
                <html>
                <body>
                    <h1>Lead Processing Error</h1>
                    <p>Lead ID: {lead_id}</p>
                    <p>Status: {status}</p>
                    <p>Error: {message}</p>
                    <p>Timestamp: {timestamp}</p>
                </body>
                </html>
                """,
                body_text="""
                Lead Processing Error
                
                Lead ID: {lead_id}
                Status: {status}
                Error: {message}
                Timestamp: {timestamp}
                """
            )
        else:
            return EmailTemplate(
                subject="Lead {lead_id} Processing {status}",
                body_html="""
                <html>
                <body>
                    <h1>Lead Processing {status}</h1>
                    <p>Lead ID: {lead_id}</p>
                    <p>Status: {status}</p>
                    <p>Message: {message}</p>
                    <p>Timestamp: {timestamp}</p>
                </body>
                </html>
                """,
                body_text="""
                Lead Processing {status}
                
                Lead ID: {lead_id}
                Status: {status}
                Message: {message}
                Timestamp: {timestamp}
                """
            )
    
    async def _send_email(self, recipients: List[EmailRecipient], subject: str,
                        body_html: Optional[str] = None, body_text: Optional[str] = None,
                        cc: List[EmailRecipient] = [], bcc: List[EmailRecipient] = []):
        """
        Send an email
        
        Args:
            recipients (List[EmailRecipient]): Recipients
            subject (str): Subject
            body_html (str, optional): HTML body. Defaults to None.
            body_text (str, optional): Text body. Defaults to None.
            cc (List[EmailRecipient], optional): CC recipients. Defaults to [].
            bcc (List[EmailRecipient], optional): BCC recipients. Defaults to [].
        """
        try:
            # Check if email configuration is available
            if not hasattr(self.config, 'email') or not self.config.email:
                self.logger.error("Email configuration not available")
                return
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.config.email.from_email
            msg['To'] = ', '.join([r.email for r in recipients])
            
            if cc:
                msg['Cc'] = ', '.join([r.email for r in cc])
            
            # Add text body
            if body_text:
                msg.attach(MIMEText(body_text, 'plain'))
            
            # Add HTML body
            if body_html:
                msg.attach(MIMEText(body_html, 'html'))
            
            # Get all recipient emails
            all_recipients = [r.email for r in recipients]
            all_recipients.extend([r.email for r in cc])
            all_recipients.extend([r.email for r in bcc])
            
            # Send email
            if self.config.email.use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.config.email.smtp_server, self.config.email.smtp_port, context=context) as server:
                    server.login(self.config.email.smtp_username, self.config.email.smtp_password)
                    server.sendmail(self.config.email.from_email, all_recipients, msg.as_string())
            else:
                with smtplib.SMTP(self.config.email.smtp_server, self.config.email.smtp_port) as server:
                    server.login(self.config.email.smtp_username, self.config.email.smtp_password)
                    server.sendmail(self.config.email.from_email, all_recipients, msg.as_string())
            
            self.logger.info(f"Email sent to {len(all_recipients)} recipients")
        
        except Exception as e:
            self.logger.error(f"Error sending email: {str(e)}")

def create_app(config_path: Optional[str] = None) -> FastAPI:
    """
    Create FastAPI application
    
    Args:
        config_path (str, optional): Path to config file. Defaults to None.
        
    Returns:
        FastAPI: FastAPI application
    """
    service = NotificationService(config_path)
    return service.app

if __name__ == "__main__":
    import uvicorn
    
    # Load configuration
    config = load_config()
    service_config = config.services["notification_service"]
    
    # Run the application
    uvicorn.run(
        "service:create_app",
        host=service_config.host,
        port=service_config.port,
        reload=service_config.debug
    )