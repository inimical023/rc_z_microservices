import base64
import time
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

from ..shared.utils import APIClient
from ..shared.models import CallLogEvent, RecordingInfo

class RingCentralClient:
    """Client for interacting with the RingCentral API"""
    
    def __init__(self, jwt_token: str, client_id: str, client_secret: str, 
                 account_id: str = "~", base_url: str = "https://platform.ringcentral.com",
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the RingCentral client
        
        Args:
            jwt_token (str): JWT token for authentication
            client_id (str): OAuth client ID
            client_secret (str): OAuth client secret
            account_id (str, optional): RingCentral account ID. Defaults to "~" (current account).
            base_url (str, optional): RingCentral API base URL. Defaults to "https://platform.ringcentral.com".
            logger (logging.Logger, optional): Logger to use. Defaults to None.
        """
        self.logger = logger or logging.getLogger(__name__)
        self.jwt_token = jwt_token
        self.client_id = client_id
        self.client_secret = client_secret
        self.account_id = account_id
        self.base_url = base_url
        self.access_token = None
        self.token_expiry = None
        self.api_client = APIClient(base_url, logger=self.logger)
        
        # Initialize token
        self._get_oauth_token()
    
    def _get_oauth_token(self) -> None:
        """Exchange JWT token for OAuth access token"""
        # Create Basic auth header
        auth_str = f"{self.client_id}:{self.client_secret}"
        auth_bytes = auth_str.encode('ascii')
        base64_auth = base64.b64encode(auth_bytes).decode('ascii')
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {base64_auth}"
        }
        
        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
            "assertion": self.jwt_token
        }
        
        try:
            response = self.api_client.request(
                method="POST",
                endpoint="restapi/oauth/token",
                headers=headers,
                data=data
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data["access_token"]
                
                # Store token expiry time if available
                if 'expires_in' in token_data:
                    # Add some buffer (subtract 60 seconds) to ensure we refresh before expiry
                    self.token_expiry = time.time() + token_data['expires_in'] - 60
                
                self.logger.debug(f"RingCentral authentication successful. Token expires in {token_data.get('expires_in', 'unknown')} seconds")
            else:
                self.logger.error(f"Failed to get OAuth token: {response.status_code} - {response.text}")
                raise Exception(f"Failed to get OAuth token: {response.status_code}")
        except Exception as e:
            self.logger.error(f"Error getting RingCentral token: {str(e)}")
            raise
    
    def _ensure_valid_token(self) -> None:
        """Ensure we have a valid access token before making API calls"""
        if not self.access_token:
            self._get_oauth_token()
        elif self.token_expiry and time.time() > self.token_expiry:
            self.logger.debug("RingCentral token expired or about to expire, refreshing")
            self._get_oauth_token()
    
    def get_call_logs(self, extension_id: str, start_date: Optional[str] = None, 
                      end_date: Optional[str] = None, call_direction: str = "Inbound",
                      call_result: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get call logs from RingCentral API for a specific extension
        
        Args:
            extension_id (str): Extension ID to get call logs for
            start_date (str, optional): Start date in ISO format. Defaults to None.
            end_date (str, optional): End date in ISO format. Defaults to None.
            call_direction (str, optional): Call direction filter. Defaults to "Inbound".
            call_result (str, optional): Call result filter (e.g., "Missed", "Completed"). Defaults to None.
            
        Returns:
            List[Dict[str, Any]]: List of call log records
        """
        self._ensure_valid_token()
        
        params = {
            'direction': call_direction,
            'type': 'Voice',
            'view': 'Detailed',
            'withRecording': 'true',  # Include recording info
            'showBlocked': 'true',
            'showDeleted': 'false',
            'perPage': 250  # Increased perPage limit
        }
        
        if start_date:
            params['dateFrom'] = start_date
        if end_date:
            params['dateTo'] = end_date
        if call_result:
            params['result'] = call_result
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        endpoint = f"restapi/v1.0/account/{self.account_id}/extension/{extension_id}/call-log"
        
        self.logger.debug(f"API Request URL: {endpoint}")
        self.logger.debug(f"API Request Parameters: {params}")
        
        # Handle pagination and API rate limits
        all_records = []
        page = 1
        
        while True:
            params['page'] = page
            
            try:
                response = self.api_client.request(
                    method="GET",
                    endpoint=endpoint,
                    headers=headers,
                    params=params
                )
                
                if response.status_code == 401:  # Unauthorized - token expired
                    self.logger.warning("Access token expired, refreshing...")
                    self._get_oauth_token()
                    headers['Authorization'] = f'Bearer {self.access_token}'
                    continue  # Retry with new token
                
                if response.status_code != 200:
                    self.logger.error(f"Error getting call logs: {response.status_code} - {response.text}")
                    break
                
                data = response.json()
                records = data.get('records', [])
                
                if not records:
                    break  # No more records
                
                all_records.extend(records)
                
                # Check if there are more pages
                navigation = data.get('navigation', {})
                if page >= navigation.get('totalPages', 1):
                    break
                
                page += 1
                
            except Exception as e:
                self.logger.error(f"Error getting call logs for extension {extension_id}: {str(e)}")
                if page > 1:  # Return what we've collected so far if we got something
                    break
                return []
        
        self.logger.info(f"Retrieved {len(all_records)} total call logs for extension {extension_id}")
        return all_records
    
    def get_recording_content(self, recording_id: str) -> Tuple[Optional[bytes], Optional[str]]:
        """
        Get recording content from RingCentral API
        
        Args:
            recording_id (str): Recording ID to get content for
            
        Returns:
            Tuple[Optional[bytes], Optional[str]]: Tuple of (content, content_type) or (None, None) if error
        """
        self._ensure_valid_token()
        
        url = f"https://media.ringcentral.com/restapi/v1.0/account/~/recording/{recording_id}/content"
        headers = {
            'Authorization': f'Bearer {self.access_token}',
        }
        
        try:
            response = self.api_client.request(
                method="GET",
                endpoint=url,
                headers=headers,
                stream=True
            )
            
            if response.status_code == 200:
                content_type = response.headers.get('Content-Type')
                self.logger.info(f"Successfully retrieved recording content for recording ID: {recording_id}")
                return response.content, content_type
            else:
                self.logger.error(
                    f"Error getting recording content for recording ID {recording_id}: {response.status_code} - {response.text}")
                return None, None
                
        except Exception as e:
            self.logger.error(f"Exception getting recording content for recording ID {recording_id}: {e}")
            return None, None
    
    def get_extension_info(self, extension_id: str) -> Optional[Dict[str, Any]]:
        """
        Get extension information from RingCentral API
        
        Args:
            extension_id (str): Extension ID to get info for
            
        Returns:
            Optional[Dict[str, Any]]: Extension info or None if error
        """
        self._ensure_valid_token()
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        endpoint = f"restapi/v1.0/account/{self.account_id}/extension/{extension_id}"
        
        try:
            response = self.api_client.request(
                method="GET",
                endpoint=endpoint,
                headers=headers
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                self.logger.error(f"Error getting extension info: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            self.logger.error(f"Exception getting extension info for extension ID {extension_id}: {e}")
            return None
    
    def get_call_queues(self) -> List[Dict[str, Any]]:
        """
        Get all call queues from RingCentral API
        
        Returns:
            List[Dict[str, Any]]: List of call queues
        """
        self._ensure_valid_token()
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        endpoint = f"restapi/v1.0/account/{self.account_id}/call-queues"
        
        try:
            response = self.api_client.request(
                method="GET",
                endpoint=endpoint,
                headers=headers
            )
            
            if response.status_code == 200:
                return response.json().get('records', [])
            else:
                self.logger.error(f"Error getting call queues: {response.status_code} - {response.text}")
                return []
                
        except Exception as e:
            self.logger.error(f"Exception getting call queues: {e}")
            return []
    
    def parse_call_log_to_event(self, call_log: Dict[str, Any]) -> CallLogEvent:
        """
        Parse a call log record into a CallLogEvent model
        
        Args:
            call_log (Dict[str, Any]): Call log record from RingCentral API
            
        Returns:
            CallLogEvent: Parsed call log event
        """
        # Parse recording info if available
        recording = None
        if 'recording' in call_log and call_log['recording']:
            recording = RecordingInfo(
                id=call_log['recording']['id'],
                contentUri=call_log['recording'].get('contentUri'),
                duration=call_log['recording'].get('duration')
            )
        
        # Parse start time
        start_time = datetime.fromisoformat(call_log['startTime'].replace('Z', '+00:00'))
        
        # Create and return CallLogEvent
        return CallLogEvent(
            id=call_log['id'],
            sessionId=call_log.get('sessionId'),
            startTime=start_time,
            duration=call_log.get('duration'),
            direction=call_log['direction'],
            result=call_log['result'],
            from_=call_log['from'],
            to=call_log['to'],
            recording=recording
        )