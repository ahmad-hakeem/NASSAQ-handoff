"""
NASSAQ — Consistent API Response Envelope
Every endpoint can return ApiResponse[T] for uniform structure.
"""
from typing import TypeVar, Generic, Optional, Any, List
from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None
    message_ar: Optional[str] = None
    errors: Optional[List[str]] = None
    meta: Optional[dict] = None


def ok(
    data: Any = None,
    *,
    message: str | None = None,
    message_ar: str | None = None,
    meta: dict | None = None,
) -> dict:
    return ApiResponse(
        success=True,
        data=data,
        message=message,
        message_ar=message_ar,
        meta=meta,
    ).model_dump(exclude_none=True)


def fail(
    *,
    message: str | None = None,
    message_ar: str | None = None,
    errors: list[str] | None = None,
) -> dict:
    return ApiResponse(
        success=False,
        message=message,
        message_ar=message_ar,
        errors=errors,
    ).model_dump(exclude_none=True)
