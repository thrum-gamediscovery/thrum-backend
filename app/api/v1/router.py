"""
Combines and registers all versioned API endpoint routers.

This keeps routing modular and clean.
"""

# app/api/v1/router.py
from fastapi import APIRouter
from .endpoints import user, game, session, chat
from app.api.v1.endpoints.whatsapp import router as whatsapp_router

api_router = APIRouter()
# api_router.include_router(user.router, prefix="/user", tags=["User"])
# api_router.include_router(game.router, prefix="/game", tags=["Game"])
api_router.include_router(session.router, prefix="/session", tags=["Session"])
api_router.include_router(whatsapp_router, prefix="/whatsapp", tags=["WhatsApp"])
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])