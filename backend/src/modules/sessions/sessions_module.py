"""
Sessions Module
= NestJS @Module()

Wires together sessions controllers, services, and repository.
Register by calling register(api_router).
"""
import logging
from fastapi import APIRouter

logger = logging.getLogger("nassaq")


def register(api_router: APIRouter) -> None:
    """Register sessions routes into api_router."""
    pass
    logger.info("SessionsModule: registered")
