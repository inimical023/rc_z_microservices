"""
Shared utilities and models for the RingCentral-Zoho microservices.
"""

from .utils import (
    setup_logging,
    normalize_phone_number,
    get_date_range,
    APIClient,
    SecureStorage
)

from .models import (
    CallDirection,
    CallResult,
    LeadStatus,
    PhoneInfo,
    RecordingInfo,
    CallLogEvent,
    LeadOwner,
    Lead,
    Note,
    Attachment,
    CallProcessingResult,
    EventMessage,
    CallLoggedEvent,
    LeadCreatedEvent,
    LeadUpdatedEvent,
    RecordingAttachedEvent,
    LeadProcessedEvent
)

from .message_broker import (
    MessageBroker,
    InMemoryMessageBroker,
    KafkaMessageBroker,
    RabbitMQMessageBroker,
    create_message_broker
)

from .config import (
    load_config,
    get_service_config,
    create_default_config,
    AppConfig,
    ServiceConfig,
    RingCentralConfig,
    ZohoConfig,
    DatabaseConfig,
    MessageBrokerConfig
)

__all__ = [
    # Utils
    'setup_logging',
    'normalize_phone_number',
    'get_date_range',
    'APIClient',
    'SecureStorage',
    
    # Models
    'CallDirection',
    'CallResult',
    'LeadStatus',
    'PhoneInfo',
    'RecordingInfo',
    'CallLogEvent',
    'LeadOwner',
    'Lead',
    'Note',
    'Attachment',
    'CallProcessingResult',
    'EventMessage',
    'CallLoggedEvent',
    'LeadCreatedEvent',
    'LeadUpdatedEvent',
    'RecordingAttachedEvent',
    'LeadProcessedEvent',
    
    # Message Broker
    'MessageBroker',
    'InMemoryMessageBroker',
    'KafkaMessageBroker',
    'RabbitMQMessageBroker',
    'create_message_broker',
    
    # Config
    'load_config',
    'get_service_config',
    'create_default_config',
    'AppConfig',
    'ServiceConfig',
    'RingCentralConfig',
    'ZohoConfig',
    'DatabaseConfig',
    'MessageBrokerConfig'
]