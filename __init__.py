"""
RingCentral-Zoho Microservices Integration.

This package provides a microservices-based integration between RingCentral and Zoho CRM.
"""

__version__ = "1.0.0"

from . import shared
from . import call_service
from . import lead_service
from . import orchestrator_service
from . import notification_service
from . import admin_service

__all__ = [
    'shared',
    'call_service',
    'lead_service',
    'orchestrator_service',
    'notification_service',
    'admin_service'
]