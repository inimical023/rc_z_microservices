import os
import json
import logging
import base64
from datetime import datetime, timedelta
from pathlib import Path
from cryptography.fernet import Fernet
import requests
import re

# Configure logging
def setup_logging(service_name, log_level=logging.INFO):
    """
    Configure logging with consistent format and handlers
    
    Args:
        service_name (str): Name of the service for the logger
        log_level (int): Logging level (default: logging.INFO)
        
    Returns:
        logging.Logger: Configured logger instance
    """
    logger = logging.getLogger(service_name)
    
    # Check if logger already has handlers to avoid duplicate output
    if logger.handlers:
        return logger
        
    logger.setLevel(log_level)
    
    # Create logs directory if it doesn't exist
    logs_dir = Path('logs')
    logs_dir.mkdir(exist_ok=True)
    
    # Create handlers
    file_handler = logging.FileHandler(logs_dir / f'{service_name}.log')
    console_handler = logging.StreamHandler()
    
    # Create formatters and add it to handlers
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers to the logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

# Phone number utilities
def normalize_phone_number(phone):
    """
    Normalize phone number to a standard format (digits only).
    E.g., +1 (555) 123-4567 -> 15551234567
    
    Args:
        phone (str): Phone number to normalize
        
    Returns:
        str: Normalized phone number
    """
    if not phone:
        return phone
    
    # Remove all non-digit characters
    digits_only = re.sub(r'\D', '', phone)
    
    # If it's a US/Canada number with 10 digits and no country code, add '1'
    if len(digits_only) == 10:
        digits_only = '1' + digits_only
        
    return digits_only

# Date utilities
def get_date_range(hours_back=None, start_date=None, end_date=None):
    """
    Get date range for processing
    
    Args:
        hours_back (int, optional): Hours to look back from current time
        start_date (str, optional): Start date in ISO format
        end_date (str, optional): End date in ISO format
        
    Returns:
        tuple: (start_date, end_date) in ISO format
    """
    if start_date and end_date:
        return start_date, end_date
    
    if hours_back:
        end_date = datetime.now()
        start_date = end_date - timedelta(hours=hours_back)
        return start_date.isoformat(), end_date.isoformat()
    
    # Default to last 24 hours
    end_date = datetime.now()
    start_date = end_date - timedelta(hours=24)
    return start_date.isoformat(), end_date.isoformat()

# HTTP utilities
class APIClient:
    """Base API client with retry logic and error handling"""
    
    def __init__(self, base_url, logger=None):
        self.base_url = base_url
        self.logger = logger or logging.getLogger(__name__)
        self.session = requests.Session()
    
    def request(self, method, endpoint, headers=None, params=None, data=None, json_data=None, 
                max_retries=3, backoff_factor=2, initial_delay=1, stream=False):
        """
        Make an HTTP request with retry logic
        
        Args:
            method (str): HTTP method (GET, POST, etc.)
            endpoint (str): API endpoint (will be appended to base_url)
            headers (dict, optional): HTTP headers
            params (dict, optional): Query parameters
            data (dict, optional): Form data
            json_data (dict, optional): JSON data
            max_retries (int, optional): Maximum number of retries
            backoff_factor (int, optional): Factor to multiply delay by after each retry
            initial_delay (int, optional): Initial delay in seconds
            stream (bool, optional): Whether to stream the response
            
        Returns:
            requests.Response: Response object
        """
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        delay = initial_delay
        
        for attempt in range(max_retries):
            try:
                response = self.session.request(
                    method=method,
                    url=url,
                    headers=headers,
                    params=params,
                    data=data,
                    json=json_data,
                    stream=stream
                )
                
                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get('Retry-After', delay))
                    self.logger.warning(f"Rate limit hit, retrying after {retry_after} seconds")
                    import time
                    time.sleep(retry_after)
                    continue
                
                # Handle server errors
                if response.status_code >= 500:
                    self.logger.warning(f"Server error: {response.status_code}, retrying in {delay} seconds")
                    import time
                    time.sleep(delay)
                    delay *= backoff_factor
                    continue
                
                return response
                
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request error (attempt {attempt+1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(delay)
                    delay *= backoff_factor
                else:
                    raise
        
        raise Exception(f"Failed after {max_retries} attempts")

# Secure storage
class SecureStorage:
    """Secure storage for credentials and configuration"""
    
    def __init__(self, service_name):
        self.service_name = service_name
        self.logger = logging.getLogger(service_name)
        
        # Create data directory if it doesn't exist
        self.data_dir = Path('data')
        self.data_dir.mkdir(exist_ok=True)
        
        # Create logs directory if it doesn't exist
        Path('logs').mkdir(exist_ok=True)
        
        self.key_file = self.data_dir / 'encryption.key'
        self.credentials_file = self.data_dir / 'credentials.enc'
        self._initialize_encryption()
    
    def _initialize_encryption(self):
        """Initialize or load encryption key"""
        try:
            if not self.key_file.exists():
                key = Fernet.generate_key()
                with open(self.key_file, 'wb') as key_file:
                    key_file.write(key)
                self.key = key
            else:
                with open(self.key_file, 'rb') as key_file:
                    self.key = key_file.read()
            self.cipher_suite = Fernet(self.key)
        except Exception as e:
            self.logger.error(f"Error initializing encryption: {str(e)}")
            raise
    
    def save_credentials(self, credentials):
        """
        Save encrypted credentials
        
        Args:
            credentials (dict): Credentials to save
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            existing_creds = self.load_credentials() or {}
            existing_creds.update(credentials)
            
            # Store timestamp for record-keeping
            existing_creds['timestamp'] = datetime.now().isoformat()
            
            json_data = json.dumps(existing_creds)
            encrypted_data = self.cipher_suite.encrypt(json_data.encode())
            
            with open(self.credentials_file, 'wb') as file:
                file.write(encrypted_data)
            return True
        except Exception as e:
            self.logger.error(f"Error saving credentials: {str(e)}")
            return False
    
    def load_credentials(self):
        """
        Load and decrypt credentials
        
        Returns:
            dict: Decrypted credentials or None if error
        """
        try:
            if not self.credentials_file.exists():
                return None
            
            with open(self.credentials_file, 'rb') as file:
                encrypted_data = file.read()
            
            decrypted_data = self.cipher_suite.decrypt(encrypted_data)
            credentials = json.loads(decrypted_data.decode())
            
            return credentials
        except Exception as e:
            self.logger.error(f"Error loading credentials: {str(e)}")
            return None