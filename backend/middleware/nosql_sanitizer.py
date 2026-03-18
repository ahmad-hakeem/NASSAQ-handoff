"""
NASSAQ NoSQL Injection Sanitizer Middleware
Strips MongoDB query operators from incoming JSON request bodies.
"""
import json
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

logger = logging.getLogger("nassaq.nosql_sanitizer")

MONGO_OPERATORS = frozenset([
    "$gt", "$gte", "$lt", "$lte", "$ne", "$in", "$nin",
    "$and", "$or", "$not", "$nor",
    "$exists", "$type", "$regex", "$options",
    "$where", "$expr", "$jsonSchema",
    "$mod", "$text", "$search",
    "$all", "$elemMatch", "$size",
    "$set", "$unset", "$inc", "$push", "$pull",
    "$rename", "$addToSet", "$pop",
])


def _contains_operators(obj) -> bool:
    if isinstance(obj, dict):
        for key in obj:
            if isinstance(key, str) and key.startswith("$") and key in MONGO_OPERATORS:
                return True
            if _contains_operators(obj[key]):
                return True
    elif isinstance(obj, list):
        for item in obj:
            if _contains_operators(item):
                return True
    return False


class NoSQLSanitizerMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH") and request.headers.get("content-type", "").startswith("application/json"):
            try:
                body_bytes = await request.body()
                if body_bytes:
                    body = json.loads(body_bytes)
                    if _contains_operators(body):
                        logger.warning(f"NoSQL injection attempt blocked from {request.client.host}: {request.url.path}")
                        return JSONResponse(
                            status_code=400,
                            content={"detail": "طلب غير صالح"}
                        )
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass

        response = await call_next(request)
        return response
