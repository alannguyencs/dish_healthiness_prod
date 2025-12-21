"""
API routes for dashboard functionality returning JSON data.

This module provides JSON-based endpoints for the dashboard where users can
view their food image queries in a calendar view.
"""

import calendar
import logging
from datetime import datetime

from fastapi import APIRouter, Request, Query, HTTPException
from fastapi.responses import JSONResponse

from src.auth import authenticate_user_from_request
from src.crud.crud_food_image_query import get_calendar_data

logger = logging.getLogger(__name__)

# Create router for dashboard endpoints
router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/")
async def dashboard(
    request: Request,
    year: int = Query(None, description="Year to display"),
    month: int = Query(None, description="Month to display"),
) -> JSONResponse:
    """
    Get dashboard calendar data with user's food analyses.

    Args:
        request (Request): FastAPI request object
        year (int): Year to display
        month (int): Month to display

    Returns:
        JSONResponse: Calendar view data

    Raises:
        HTTPException: 401 if not authenticated
    """
    user = authenticate_user_from_request(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")

    now = datetime.now()
    display_month = month or now.month
    display_year = year or now.year

    # Validate month and year
    if not 1 <= display_month <= 12:
        display_month = now.month
    if display_year < 2020 or display_year > now.year + 1:
        display_year = now.year

    # Get record counts for each day in the month
    record_counts = get_calendar_data(user.id, display_year, display_month)

    # Build calendar structure
    cal = calendar.Calendar(firstweekday=0)  # Monday first
    month_days = cal.monthdayscalendar(display_year, display_month)

    calendar_data = []
    for week in month_days:
        week_data = []
        for day in week:
            day_info = {"day": day, "count": 0, "is_current_month": day != 0, "is_today": False}

            if day != 0:
                date_obj = datetime(display_year, display_month, day).date()

                # Check if this is today
                if date_obj == now.date():
                    day_info["is_today"] = True

                # Get record count for this date
                date_str = date_obj.strftime("%Y-%m-%d")
                day_info["count"] = record_counts.get(date_str, 0)

            week_data.append(day_info)
        calendar_data.append(week_data)

    # Calculate navigation
    if display_month == 1:
        prev_month, prev_year = 12, display_year - 1
    else:
        prev_month, prev_year = display_month - 1, display_year

    if display_month == 12:
        next_month, next_year = 1, display_year + 1
    else:
        next_month, next_year = display_month + 1, display_year

    month_name = calendar.month_name[display_month]

    return JSONResponse(
        content={
            "calendar_data": calendar_data,
            "month_name": month_name,
            "display_year": display_year,
            "display_month": display_month,
            "prev_year": prev_year,
            "prev_month": prev_month,
            "next_year": next_year,
            "next_month": next_month,
            "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        }
    )
