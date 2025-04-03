"""
Notification Service for RingCentral-Zoho integration.

This service handles sending email notifications when leads are processed.
"""

from .service import NotificationService, create_app

__all__ = [
    'NotificationService',
    'create_app'
]