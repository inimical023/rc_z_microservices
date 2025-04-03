import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional, List, Union
from pydantic import BaseModel, Field, field_validator

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

class ServiceConfig(BaseModel):
    """Service configuration"""
    name: str
    host: str = "0.0.0.0"
    port: int
    log_level: str = "INFO"
    debug: bool = False

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

class MessageBrokerConfig(BaseModel):
    """Message broker configuration"""
    type: str
    host: str
    port: int
    username: str
    password: str

class AppConfig(BaseModel):
    """Application configuration"""
    ringcentral: RingCentralConfig
    zoho: ZohoConfig
    message_broker: MessageBrokerConfig
    services: Dict[str, ServiceConfig] = {}

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
    
    # Try multiple paths if none provided
    if not config_path:
        possible_paths = [
            "/app/config.json",                  # Container path
            "config.json",                       # Current directory
            "../config.json",                    # Parent directory
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "../config.json")  # Relative to script
        ]
        for path in possible_paths:
            logger.info(f"Trying config path: {path}")
            if os.path.exists(path):
                config_path = path
                logger.info(f"Found config at: {path}")
                break
    
    # Load config from file if path provided or found
    config_data = {}
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, "r") as f:
                config_data = json.load(f)
            logger.debug(f"Loaded configuration from {config_path}")
        except Exception as e:
            logger.error(f"Error loading configuration from {config_path}: {e}")
    
    # Override with environment variables
    # RingCentral
    if os.environ.get("RINGCENTRAL_JWT_TOKEN"):
        config_data.setdefault("ringcentral", {})["jwt_token"] = os.environ.get("RINGCENTRAL_JWT_TOKEN")
    if os.environ.get("RINGCENTRAL_CLIENT_ID"):
        config_data.setdefault("ringcentral", {})["client_id"] = os.environ.get("RINGCENTRAL_CLIENT_ID")
    if os.environ.get("RINGCENTRAL_CLIENT_SECRET"):
        config_data.setdefault("ringcentral", {})["client_secret"] = os.environ.get("RINGCENTRAL_CLIENT_SECRET")
    if os.environ.get("RINGCENTRAL_ACCOUNT_ID"):
        config_data.setdefault("ringcentral", {})["account_id"] = os.environ.get("RINGCENTRAL_ACCOUNT_ID")
    if os.environ.get("RINGCENTRAL_BASE_URL"):
        config_data.setdefault("ringcentral", {})["base_url"] = os.environ.get("RINGCENTRAL_BASE_URL")
    
    # Zoho
    if os.environ.get("ZOHO_CLIENT_ID"):
        config_data.setdefault("zoho", {})["client_id"] = os.environ.get("ZOHO_CLIENT_ID")
    if os.environ.get("ZOHO_CLIENT_SECRET"):
        config_data.setdefault("zoho", {})["client_secret"] = os.environ.get("ZOHO_CLIENT_SECRET")
    if os.environ.get("ZOHO_REFRESH_TOKEN"):
        config_data.setdefault("zoho", {})["refresh_token"] = os.environ.get("ZOHO_REFRESH_TOKEN")
    if os.environ.get("ZOHO_BASE_URL"):
        config_data.setdefault("zoho", {})["base_url"] = os.environ.get("ZOHO_BASE_URL")
    
    # Message broker
    if os.environ.get("MESSAGE_BROKER_TYPE"):
        config_data.setdefault("message_broker", {})["type"] = os.environ.get("MESSAGE_BROKER_TYPE")
    if os.environ.get("RABBITMQ_HOST"):
        config_data.setdefault("message_broker", {})["host"] = os.environ.get("RABBITMQ_HOST")
    if os.environ.get("RABBITMQ_PORT"):
        config_data.setdefault("message_broker", {})["port"] = int(os.environ.get("RABBITMQ_PORT"))
    if os.environ.get("RABBITMQ_USERNAME"):
        config_data.setdefault("message_broker", {})["username"] = os.environ.get("RABBITMQ_USERNAME")
    if os.environ.get("RABBITMQ_PASSWORD"):
        config_data.setdefault("message_broker", {})["password"] = os.environ.get("RABBITMQ_PASSWORD")
    
    # Create the config object
    try:
        config = AppConfig(**config_data)
        logger.debug("Configuration loaded successfully")
        return config
    except Exception as e:
        logger.error(f"Error creating configuration object: {e}")
        raise 