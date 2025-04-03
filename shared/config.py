import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field, validator
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class RingCentralConfig(BaseModel):
    """RingCentral API configuration"""
    jwt_token: str
    client_id: str
    client_secret: str
    account_id: str = "~"
    base_url: str = "https://platform.ringcentral.com"

class ZohoConfig(BaseModel):
    """Zoho CRM API configuration"""
    client_id: str
    client_secret: str
    refresh_token: str
    base_url: str = "https://www.zohoapis.com/crm/v7"

class DatabaseConfig(BaseModel):
    """Database configuration"""
    uri: str
    pool_size: int = 5
    max_overflow: int = 10
    pool_timeout: int = 30
    pool_recycle: int = 3600
    echo: bool = False

class MessageBrokerConfig(BaseModel):
    """Message broker configuration"""
    type: str
    host: Optional[str] = None
    port: Optional[int] = None
    username: Optional[str] = None
    password: Optional[str] = None
    virtual_host: Optional[str] = None
    bootstrap_servers: Optional[str] = None
    client_id: Optional[str] = None
    
    @validator('type')
    def validate_type(cls, v):
        """Validate message broker type"""
        valid_types = ['memory', 'kafka', 'rabbitmq']
        if v not in valid_types:
            raise ValueError(f"Invalid message broker type: {v}. Must be one of {valid_types}")
        return v
    
    @validator('bootstrap_servers')
    def validate_bootstrap_servers(cls, v, values):
        """Validate bootstrap servers for Kafka"""
        if values.get('type') == 'kafka' and not v:
            raise ValueError("bootstrap_servers is required for Kafka")
        return v
    
    @validator('host')
    def validate_host(cls, v, values):
        """Validate host for RabbitMQ"""
        if values.get('type') == 'rabbitmq' and not v:
            raise ValueError("host is required for RabbitMQ")
        return v

class ServiceConfig(BaseModel):
    """Base service configuration"""
    name: str
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    debug: bool = False
    
    @validator('log_level')
    def validate_log_level(cls, v):
        """Validate log level"""
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return v

class AppConfig(BaseModel):
    """Application configuration"""
    ringcentral: RingCentralConfig
    zoho: ZohoConfig
    database: Optional[DatabaseConfig] = None
    message_broker: MessageBrokerConfig
    services: Dict[str, ServiceConfig]
    
    class Config:
        """Pydantic config"""
        extra = "allow"

def load_config(config_path: Optional[str] = None) -> AppConfig:
    """
    Load configuration from environment variables and config file
    
    Args:
        config_path (str, optional): Path to config file
        
    Returns:
        AppConfig: Application configuration
    """
    # Initialize logger
    logger = logging.getLogger(__name__)
    
    # Load config from file if provided
    config_data = {}
    if config_path:
        config_file = Path(config_path)
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    config_data = json.load(f)
                logger.info(f"Loaded configuration from {config_file}")
            except Exception as e:
                logger.error(f"Error loading configuration from {config_file}: {e}")
    
    # Override with environment variables
    # RingCentral config
    rc_config = {
        "jwt_token": os.environ.get("RC_JWT_TOKEN", config_data.get("ringcentral", {}).get("jwt_token", "")),
        "client_id": os.environ.get("RC_CLIENT_ID", config_data.get("ringcentral", {}).get("client_id", "")),
        "client_secret": os.environ.get("RC_CLIENT_SECRET", config_data.get("ringcentral", {}).get("client_secret", "")),
        "account_id": os.environ.get("RC_ACCOUNT_ID", config_data.get("ringcentral", {}).get("account_id", "~")),
        "base_url": os.environ.get("RC_BASE_URL", config_data.get("ringcentral", {}).get("base_url", "https://platform.ringcentral.com"))
    }
    
    # Zoho config
    zoho_config = {
        "client_id": os.environ.get("ZOHO_CLIENT_ID", config_data.get("zoho", {}).get("client_id", "")),
        "client_secret": os.environ.get("ZOHO_CLIENT_SECRET", config_data.get("zoho", {}).get("client_secret", "")),
        "refresh_token": os.environ.get("ZOHO_REFRESH_TOKEN", config_data.get("zoho", {}).get("refresh_token", "")),
        "base_url": os.environ.get("ZOHO_BASE_URL", config_data.get("zoho", {}).get("base_url", "https://www.zohoapis.com/crm/v7"))
    }
    
    # Database config
    db_config = None
    if "database" in config_data or "DATABASE_URI" in os.environ:
        db_config = {
            "uri": os.environ.get("DATABASE_URI", config_data.get("database", {}).get("uri", "")),
            "pool_size": int(os.environ.get("DATABASE_POOL_SIZE", config_data.get("database", {}).get("pool_size", 5))),
            "max_overflow": int(os.environ.get("DATABASE_MAX_OVERFLOW", config_data.get("database", {}).get("max_overflow", 10))),
            "pool_timeout": int(os.environ.get("DATABASE_POOL_TIMEOUT", config_data.get("database", {}).get("pool_timeout", 30))),
            "pool_recycle": int(os.environ.get("DATABASE_POOL_RECYCLE", config_data.get("database", {}).get("pool_recycle", 3600))),
            "echo": os.environ.get("DATABASE_ECHO", "").lower() == "true" or config_data.get("database", {}).get("echo", False)
        }
    
    # Message broker config
    broker_type = os.environ.get("MESSAGE_BROKER_TYPE", config_data.get("message_broker", {}).get("type", "memory"))
    broker_config = {
        "type": broker_type
    }
    
    if broker_type == "kafka":
        broker_config.update({
            "bootstrap_servers": os.environ.get("KAFKA_BOOTSTRAP_SERVERS", config_data.get("message_broker", {}).get("bootstrap_servers", "localhost:9092")),
            "client_id": os.environ.get("KAFKA_CLIENT_ID", config_data.get("message_broker", {}).get("client_id", "rc-zoho"))
        })
    elif broker_type == "rabbitmq":
        broker_config.update({
            "host": os.environ.get("RABBITMQ_HOST", config_data.get("message_broker", {}).get("host", "localhost")),
            "port": int(os.environ.get("RABBITMQ_PORT", config_data.get("message_broker", {}).get("port", 5672))),
            "username": os.environ.get("RABBITMQ_USERNAME", config_data.get("message_broker", {}).get("username", "guest")),
            "password": os.environ.get("RABBITMQ_PASSWORD", config_data.get("message_broker", {}).get("password", "guest")),
            "virtual_host": os.environ.get("RABBITMQ_VHOST", config_data.get("message_broker", {}).get("virtual_host", "/"))
        })
    
    # Service configs
    services = config_data.get("services", {})
    
    # Override service configs with environment variables
    for service_name, service_config in services.items():
        env_prefix = service_name.upper().replace("-", "_")
        service_config["host"] = os.environ.get(f"{env_prefix}_HOST", service_config.get("host", "0.0.0.0"))
        service_config["port"] = int(os.environ.get(f"{env_prefix}_PORT", service_config.get("port", 8000)))
        service_config["log_level"] = os.environ.get(f"{env_prefix}_LOG_LEVEL", service_config.get("log_level", "INFO"))
        service_config["debug"] = os.environ.get(f"{env_prefix}_DEBUG", "").lower() == "true" or service_config.get("debug", False)
    
    # Create final config
    config = {
        "ringcentral": rc_config,
        "zoho": zoho_config,
        "message_broker": broker_config,
        "services": services
    }
    
    if db_config:
        config["database"] = db_config
    
    # Validate and return config
    try:
        return AppConfig(**config)
    except Exception as e:
        logger.error(f"Error validating configuration: {e}")
        raise

def get_service_config(config: AppConfig, service_name: str) -> ServiceConfig:
    """
    Get configuration for a specific service
    
    Args:
        config (AppConfig): Application configuration
        service_name (str): Name of the service
        
    Returns:
        ServiceConfig: Service configuration
    """
    if service_name not in config.services:
        raise ValueError(f"Service {service_name} not found in configuration")
    
    return config.services[service_name]

def create_default_config(output_path: str = "config.json"):
    """
    Create a default configuration file
    
    Args:
        output_path (str): Path to output file
    """
    default_config = {
        "ringcentral": {
            "jwt_token": "",
            "client_id": "",
            "client_secret": "",
            "account_id": "~",
            "base_url": "https://platform.ringcentral.com"
        },
        "zoho": {
            "client_id": "",
            "client_secret": "",
            "refresh_token": "",
            "base_url": "https://www.zohoapis.com/crm/v7"
        },
        "database": {
            "uri": "sqlite:///data/rc_zoho.db",
            "pool_size": 5,
            "max_overflow": 10,
            "pool_timeout": 30,
            "pool_recycle": 3600,
            "echo": False
        },
        "message_broker": {
            "type": "memory"
        },
        "services": {
            "call_service": {
                "name": "call_service",
                "host": "0.0.0.0",
                "port": 8001,
                "log_level": "INFO",
                "debug": False
            },
            "lead_service": {
                "name": "lead_service",
                "host": "0.0.0.0",
                "port": 8002,
                "log_level": "INFO",
                "debug": False
            },
            "orchestrator_service": {
                "name": "orchestrator_service",
                "host": "0.0.0.0",
                "port": 8003,
                "log_level": "INFO",
                "debug": False
            },
            "admin_service": {
                "name": "admin_service",
                "host": "0.0.0.0",
                "port": 8000,
                "log_level": "INFO",
                "debug": False
            },
            "notification_service": {
                "name": "notification_service",
                "host": "0.0.0.0",
                "port": 8004,
                "log_level": "INFO",
                "debug": False
            }
        }
    }
    
    with open(output_path, 'w') as f:
        json.dump(default_config, f, indent=2)