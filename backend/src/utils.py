"""
Utility functions for the application.

This module provides helper functions for common operations.
"""

import logging

logger = logging.getLogger(__name__)


def format_datetime(dt):
    """
    Format datetime for display.

    Args:
        dt: datetime object

    Returns:
        str: Formatted datetime string
    """
    if dt is None:
        return ""
    return dt.strftime("%Y-%m-%d %H:%M:%S")

