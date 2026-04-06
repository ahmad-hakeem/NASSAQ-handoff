"""
NASSAQ — Consistent API Response Envelope
Standard shape: { success, data, error: { code, message }, meta }
"""
from typing import TypeVar, Generic, Optional, Any
from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    code: str
    message: str
    message_ar: Optional[str] = None


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    error: Optional[ErrorDetail] = None
    meta: Optional[dict] = None


def ok(
    data: Any = None,
    *,
    meta: dict | None = None,
) -> dict:
    return ApiResponse(
        success=True,
        data=data,
        meta=meta,
    ).model_dump(exclude_none=True)


def fail(
    *,
    code: str = "INTERNAL_ERROR",
    message: str = "An error occurred",
    message_ar: str | None = None,
    status_code: int = 400,
) -> dict:
    return ApiResponse(
        success=False,
        error=ErrorDetail(code=code, message=message, message_ar=message_ar),
    ).model_dump(exclude_none=True)
