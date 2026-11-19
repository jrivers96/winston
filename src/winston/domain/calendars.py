"""Calendar domain models."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from winston.domain.identities import BusinessDate


class CalendarDate(BaseModel):
    """A single date entry in a calculation calendar."""
    
    business_date: BusinessDate = Field(..., description="The business date")
    label: Optional[str] = Field(None, description="Human-readable label (e.g., D1, D2)")
    is_calculation_day: bool = Field(True, description="Whether calculations run on this date")
    previous_calculation_date: Optional[BusinessDate] = Field(
        None, description="Previous calculation date per calendar rules"
    )
    timezone: str = Field("UTC", description="Timezone for this date")
    
    # Closure info
    closure_reason: Optional[str] = Field(None, description="Reason if not a calculation day")
    
    # Metadata
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class CalendarConfig(BaseModel):
    """Configuration for a calculation calendar."""
    
    id: str = Field(..., description="Calendar identifier")
    description: Optional[str] = Field(None, description="Calendar description")
    timezone: str = Field("UTC", description="Default timezone")
    
    # Rules
    weekday_rule: Optional[str] = Field(None, description="Weekday rule (e.g., Mon-Fri)")
    holiday_source: Optional[str] = Field(None, description="Reference to holiday calendar")
    custom_closures: List[date] = Field(
        default_factory=list, description="Additional closure dates"
    )
    
    # Dates - for synthetic profiles with explicit date list
    dates: List[CalendarDate] = Field(
        default_factory=list, description="Explicit date entries"
    )
    
    # Version tracking
    version: Optional[str] = Field(None, description="Calendar version")
    effective_from: Optional[datetime] = Field(None, description="When this version became effective")
    
    def get_previous_calculation_date(self, business_date: BusinessDate) -> Optional[BusinessDate]:
        """Get the previous calculation date for a given date.
        
        Uses explicit mappings in dates list, or falls back to calendar rules.
        """
        # First check explicit dates
        for cal_date in self.dates:
            if cal_date.business_date == business_date:
                return cal_date.previous_calculation_date
        
        # If not in explicit list, would need to apply rules
        # For now, return None to indicate unknown
        return None
    
    def is_calculation_day(self, business_date: BusinessDate) -> bool:
        """Check if a date is a calculation day."""
        # Check explicit dates first
        for cal_date in self.dates:
            if cal_date.business_date == business_date:
                return cal_date.is_calculation_day
        
        # Check custom closures
        if business_date in self.custom_closures:
            return False
        
        # Would need to check weekday rules and holidays
        # Default to True for unlisted dates
        return True
    
    def get_date_label(self, business_date: BusinessDate) -> Optional[str]:
        """Get the label for a date if one exists."""
        for cal_date in self.dates:
            if cal_date.business_date == business_date:
                return cal_date.label
        return None
