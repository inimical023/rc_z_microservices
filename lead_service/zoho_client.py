import time
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from datetime import datetime

from ..shared.utils import APIClient, normalize_phone_number
from ..shared.models import Lead, Note, Attachment, LeadOwner

class ZohoClient:
    """Client for interacting with the Zoho CRM API"""
    
    def __init__(self, client_id: str, client_secret: str, refresh_token: str,
                 base_url: str = "https://www.zohoapis.com/crm/v7",
                 logger: Optional[logging.Logger] = None):
        """
        Initialize the Zoho client
        
        Args:
            client_id (str): OAuth client ID
            client_secret (str): OAuth client secret
            refresh_token (str): OAuth refresh token
            base_url (str, optional): Zoho CRM API base URL. Defaults to "https://www.zohoapis.com/crm/v7".
            logger (logging.Logger, optional): Logger to use. Defaults to None.
        """
        self.logger = logger or logging.getLogger(__name__)
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.base_url = base_url
        self.access_token = None
        self.token_expiry = None
        self.api_client = APIClient(base_url, logger=self.logger)
        
        # Initialize token
        self._get_access_token()
    
    def _get_access_token(self) -> None:
        """Get access token using refresh token"""
        url = "https://accounts.zoho.com/oauth/v2/token"
        data = {
            "refresh_token": self.refresh_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "refresh_token"
        }
        
        try:
            response = self.api_client.request(
                method="POST",
                endpoint=url,
                data=data
            )
            
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data["access_token"]
                
                # Store token expiry time if available
                if 'expires_in' in token_data:
                    # Add some buffer (subtract 60 seconds) to ensure we refresh before expiry
                    self.token_expiry = time.time() + token_data['expires_in'] - 60
                
                self.logger.debug(f"Zoho authentication successful. Token expires in {token_data.get('expires_in', 'unknown')} seconds")
            else:
                self.logger.error(f"Failed to get access token: {response.status_code} - {response.text}")
                raise Exception(f"Failed to get access token: {response.status_code}")
        except Exception as e:
            self.logger.error(f"Error getting Zoho token: {str(e)}")
            raise
    
    def _ensure_valid_token(self) -> None:
        """Ensure we have a valid access token before making API calls"""
        if not self.access_token:
            self._get_access_token()
        elif self.token_expiry and time.time() > self.token_expiry:
            self.logger.debug("Zoho token expired or about to expire, refreshing")
            self._get_access_token()
    
    def search_leads_by_phone(self, phone_number: str) -> List[Dict[str, Any]]:
        """
        Search for leads by phone number
        
        Args:
            phone_number (str): Phone number to search for
            
        Returns:
            List[Dict[str, Any]]: List of matching leads
        """
        self._ensure_valid_token()
        
        # Normalize phone number
        normalized_phone = normalize_phone_number(phone_number)
        
        # Try different phone formats
        phone_formats = [
            normalized_phone,  # Full format with country code (e.g., 15551234567)
            normalized_phone[-10:]  # Without country code (e.g., 5551234567)
        ]
        
        # Add original format if different
        if phone_number not in phone_formats:
            phone_formats.append(phone_number)
        
        # Search for each format
        for phone_format in phone_formats:
            try:
                results = self._search_records("Leads", f"Phone:equals:{phone_format}")
                
                if results:
                    self.logger.debug(f"Found {len(results)} leads with phone {phone_format}")
                    return results
            except Exception as e:
                self.logger.error(f"Error searching leads by phone {phone_format}: {str(e)}")
        
        self.logger.debug(f"No leads found with phone {phone_number}")
        return []
    
    def _search_records(self, module: str, criteria: str) -> List[Dict[str, Any]]:
        """
        Search for records in Zoho CRM
        
        Args:
            module (str): Module to search in (e.g., "Leads")
            criteria (str): Search criteria (e.g., "Phone:equals:5551234567")
            
        Returns:
            List[Dict[str, Any]]: List of matching records
        """
        self._ensure_valid_token()
        
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.access_token}"
        }
        
        params = {
            "criteria": criteria
        }
        
        try:
            response = self.api_client.request(
                method="GET",
                endpoint=f"{module}/search",
                headers=headers,
                params=params
            )
            
            if response.status_code == 200:
                return response.json().get('data', [])
            elif response.status_code == 204:  # No content
                return []
            else:
                self.logger.error(f"Error searching records: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            self.logger.error(f"Exception searching records: {str(e)}")
            return []
    
    def create_lead(self, lead: Lead) -> Optional[str]:
        """
        Create a new lead in Zoho CRM
        
        Args:
            lead (Lead): Lead data
            
        Returns:
            Optional[str]: Lead ID if successful, None otherwise
        """
        self._ensure_valid_token()
        
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
            "Content-Type": "application/json"
        }
        
        # Convert Lead model to dict for API
        lead_dict = lead.dict(exclude_none=True, by_alias=True)
        
        # Handle owner field
        if lead.owner:
            lead_dict["Owner"] = {"id": lead.owner.id}
            
            # Remove owner from dict to avoid duplicate fields
            if "owner" in lead_dict:
                del lead_dict["owner"]
        
        # Prepare request data
        data = {
            "data": [lead_dict]
        }
        
        try:
            response = self.api_client.request(
                method="POST",
                endpoint="Leads",
                headers=headers,
                json_data=data
            )
            
            if response.status_code in [200, 201, 202]:
                result = response.json()
                if result.get('data') and len(result['data']) > 0:
                    lead_id = result['data'][0].get('details', {}).get('id')
                    self.logger.info(f"Created lead with ID: {lead_id}")
                    return lead_id
                else:
                    self.logger.error(f"No lead ID returned in response: {result}")
                    return None
            else:
                self.logger.error(f"Error creating lead: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            self.logger.error(f"Exception creating lead: {str(e)}")
            return None
    
    def update_lead(self, lead_id: str, lead_data: Dict[str, Any]) -> bool:
        """
        Update an existing lead in Zoho CRM
        
        Args:
            lead_id (str): Lead ID to update
            lead_data (Dict[str, Any]): Lead data to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        self._ensure_valid_token()
        
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
            "Content-Type": "application/json"
        }
        
        # Handle owner field
        if "owner" in lead_data and isinstance(lead_data["owner"], dict) and "id" in lead_data["owner"]:
            lead_data["Owner"] = {"id": lead_data["owner"]["id"]}
            del lead_data["owner"]
        
        # Prepare request data
        data = {
            "data": [lead_data]
        }
        
        try:
            response = self.api_client.request(
                method="PUT",
                endpoint=f"Leads/{lead_id}",
                headers=headers,
                json_data=data
            )
            
            if response.status_code in [200, 202]:
                self.logger.info(f"Updated lead with ID: {lead_id}")
                return True
            else:
                self.logger.error(f"Error updating lead: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            self.logger.error(f"Exception updating lead: {str(e)}")
            return False
    
    def add_note_to_lead(self, lead_id: str, note_content: str, title: Optional[str] = None) -> Optional[str]:
        """
        Add a note to a lead in Zoho CRM
        
        Args:
            lead_id (str): Lead ID to add note to
            note_content (str): Note content
            title (str, optional): Note title. Defaults to None.
            
        Returns:
            Optional[str]: Note ID if successful, None otherwise
        """
        self._ensure_valid_token()
        
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.access_token}",
            "Content-Type": "application/json"
        }
        
        # Prepare note data
        note_data = {
            "Parent_Id": lead_id,
            "Note_Title": title or f"Note added on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "Note_Content": note_content
        }
        
        # Prepare request data
        data = {
            "data": [note_data]
        }
        
        try:
            response = self.api_client.request(
                method="POST",
                endpoint="Notes",
                headers=headers,
                json_data=data
            )
            
            if response.status_code in [200, 201, 202]:
                result = response.json()
                if result.get('data') and len(result['data']) > 0:
                    note_id = result['data'][0].get('details', {}).get('id')
                    self.logger.info(f"Added note with ID: {note_id} to lead: {lead_id}")
                    return note_id
                else:
                    self.logger.error(f"No note ID returned in response: {result}")
                    return None
            else:
                self.logger.error(f"Error adding note: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            self.logger.error(f"Exception adding note: {str(e)}")
            return None
    
    def attach_file_to_lead(self, lead_id: str, file_name: str, file_content: bytes, 
                           content_type: str) -> Optional[str]:
        """
        Attach a file to a lead in Zoho CRM
        
        Args:
            lead_id (str): Lead ID to attach file to
            file_name (str): File name
            file_content (bytes): File content
            content_type (str): File content type
            
        Returns:
            Optional[str]: Attachment ID if successful, None otherwise
        """
        self._ensure_valid_token()
        
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.access_token}"
        }
        
        # Prepare files for multipart upload
        files = {
            'file': (file_name, file_content, content_type)
        }
        
        try:
            response = self.api_client.request(
                method="POST",
                endpoint=f"Leads/{lead_id}/Attachments",
                headers=headers,
                files=files
            )
            
            if response.status_code in [200, 201, 202]:
                result = response.json()
                if result.get('data') and len(result['data']) > 0:
                    attachment_id = result['data'][0].get('details', {}).get('id')
                    self.logger.info(f"Attached file with ID: {attachment_id} to lead: {lead_id}")
                    return attachment_id
                else:
                    self.logger.error(f"No attachment ID returned in response: {result}")
                    return None
            else:
                self.logger.error(f"Error attaching file: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            self.logger.error(f"Exception attaching file: {str(e)}")
            return None
    
    def is_file_already_attached(self, lead_id: str, file_name: str) -> bool:
        """
        Check if a file is already attached to a lead
        
        Args:
            lead_id (str): Lead ID to check
            file_name (str): File name to check for
            
        Returns:
            bool: True if file is already attached, False otherwise
        """
        self._ensure_valid_token()
        
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.access_token}"
        }
        
        params = {
            "fields": "id,File_Name"
        }
        
        try:
            response = self.api_client.request(
                method="GET",
                endpoint=f"Leads/{lead_id}/Attachments",
                headers=headers,
                params=params
            )
            
            if response.status_code == 200:
                attachments = response.json().get('data', [])
                for attachment in attachments:
                    if file_name in attachment.get('File_Name', ''):
                        return True
                return False
            else:
                self.logger.error(f"Error checking attachments: {response.status_code} - {response.text}")
                return False
        except Exception as e:
            self.logger.error(f"Exception checking attachments: {str(e)}")
            return False
    
    def get_users(self) -> List[Dict[str, Any]]:
        """
        Get all active users from Zoho CRM
        
        Returns:
            List[Dict[str, Any]]: List of users
        """
        self._ensure_valid_token()
        
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.access_token}"
        }
        
        try:
            response = self.api_client.request(
                method="GET",
                endpoint="users",
                headers=headers
            )
            
            if response.status_code == 200:
                users = response.json().get('users', [])
                # Filter active users
                active_users = [user for user in users if user.get('status') == 'active']
                self.logger.info(f"Retrieved {len(active_users)} active users")
                return active_users
            else:
                self.logger.error(f"Error getting users: {response.status_code} - {response.text}")
                return []
        except Exception as e:
            self.logger.error(f"Exception getting users: {str(e)}")
            return []
    
    def get_lead_owner_by_email(self, email: str) -> Optional[LeadOwner]:
        """
        Get lead owner by email
        
        Args:
            email (str): Email of the lead owner
            
        Returns:
            Optional[LeadOwner]: Lead owner if found, None otherwise
        """
        users = self.get_users()
        
        for user in users:
            if user.get('email') == email:
                return LeadOwner(
                    id=user.get('id'),
                    name=user.get('full_name'),
                    email=user.get('email')
                )
        
        return None
    
    def get_lead_by_id(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """
        Get lead by ID
        
        Args:
            lead_id (str): Lead ID
            
        Returns:
            Optional[Dict[str, Any]]: Lead data if found, None otherwise
        """
        self._ensure_valid_token()
        
        headers = {
            "Authorization": f"Zoho-oauthtoken {self.access_token}"
        }
        
        try:
            response = self.api_client.request(
                method="GET",
                endpoint=f"Leads/{lead_id}",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json().get('data', [])
                if data and len(data) > 0:
                    return data[0]
                else:
                    self.logger.error(f"No lead found with ID: {lead_id}")
                    return None
            else:
                self.logger.error(f"Error getting lead: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            self.logger.error(f"Exception getting lead: {str(e)}")
            return None