"""
Admin Service for RingCentral-Zoho integration.

This service provides a web-based admin interface for managing the RingCentral-Zoho integration.
"""

from .service import AdminService, create_app

__all__ = [
    'AdminService',
    'create_app'
]