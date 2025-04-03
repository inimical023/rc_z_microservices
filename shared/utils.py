import os
import re
import json
import logging
import requests
from typing import Dict, Any, Optional, List, Union
from datetime import datetime

def setup_logging(name: str, log_level: Optional[str] = None) -> logging.Logger:
    """
    Set up logging
    
    Args:
        name (str): Logger name
        log_level (str, optional): Log level. Defaults to None.
        
    Returns:
        logging.Logger: Logger instance
    """
    # Get log level
    log_level = log_level or os.environ.get("LOG_LEVEL", "INFO")
    
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Create file handler if log directory exists
    os.makedirs("logs", exist_ok=True)
    file_handler = logging.FileHandler(f"logs/{name}.log")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    return logger

def normalize_phone_number(phone: Optional[str]) -> Optional[str]:
    """
    Normalize phone number to a standard format.
    
    Args:
        phone (str): Phone number to normalize
        
    Returns:
        str: Normalized phone number
    """
    if not phone:
        return phone
    
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    
    # If it's a 10-digit number, assume US/Canada and add country code
    if len(digits_only) == 10:
        digits_only = '1' + digits_only
    
    return digits_only

class APIClient:
    """Generic API client"""
    
    def __init__(self, base_url: str, logger: Optional[logging.Logger] = None):
        """
        Initialize the API client
        
        Args:
            base_url (str): Base URL for API
            logger (logging.Logger, optional): Logger to use. Defaults to None.
        """
        self.base_url = base_url
        self.logger = logger or logging.getLogger(__name__)
    
    def request(self, method: str, endpoint: str, 
                headers: Optional[Dict[str, str]] = None, 
                params: Optional[Dict[str, Any]] = None,
                data: Optional[Dict[str, Any]] = None,
                json_data: Optional[Dict[str, Any]] = None,
                files: Optional[Dict[str, Any]] = None,
                timeout: int = 30) -> requests.Response:
        """
        Make an HTTP request
        
        Args:
            method (str): HTTP method (GET, POST, PUT, DELETE)
            endpoint (str): API endpoint
            headers (Dict[str, str], optional): HTTP headers. Defaults to None.
            params (Dict[str, Any], optional): Query parameters. Defaults to None.
            data (Dict[str, Any], optional): Form data. Defaults to None.
            json_data (Dict[str, Any], optional): JSON data. Defaults to None.
            files (Dict[str, Any], optional): Files to upload. Defaults to None.
            timeout (int, optional): Request timeout in seconds. Defaults to 30.
            
        Returns:
            requests.Response: Response object
        """
        # Construct URL
        url = endpoint if endpoint.startswith('http') else f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Make request
        self.logger.debug(f"Making {method} request to {url}")
        response = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            data=data,
            json=json_data,
            files=files,
            timeout=timeout
        )
        
        # Log response
        self.logger.debug(f"Response status code: {response.status_code}")
        
        # Return response
        return response 