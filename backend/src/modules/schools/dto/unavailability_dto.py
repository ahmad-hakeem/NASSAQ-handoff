"""
NASSAQ - Unavailability DTOs
Pydantic models for teacher/class unavailability, short/long-term absence, relocation, and acknowledgment.
"""
from pydantic import BaseModel, model_validator
from typing import Optional, List


class UnavailabilityCreate(BaseModel):
    entity_type: str
    entity_id: str
    entity_name: Optional[str] = None
    unavailability_type: str = "recurring"
    day: Optional[str] = None
    period: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    reason: Optional[str] = None
    alternative_location: Optional[str] = None

    @model_validator(mode="after")
    def validate_unavailability_fields(self):
        if self.unavailability_type == "recurring":
            if not self.day or not self.period:
                raise ValueError("عدم التوفر المتكرر يتطلب تحديد اليوم والحصة")
        elif self.unavailability_type == "long_term":
            if not self.start_date or not self.end_date:
                raise ValueError("فترة عدم التوفر طويلة الأمد تتطلب تحديد تاريخ البداية والنهاية")
            if self.start_date > self.end_date:
                raise ValueError("تاريخ النهاية يجب أن يكون بعد تاريخ البداية")
        return self


class AcknowledgeRelocationRequest(BaseModel):
    unavailability_id: str
