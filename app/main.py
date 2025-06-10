"""
Main entry point for the FastAPI application.

- Initializes the FastAPI app
- Includes all API routers
- Adds CORS middleware
"""

# app/main.py
from fastapi import FastAPI
from app.api.v1.router import api_router

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Thrum Backend")

# Allow CORS for all origins (adjust in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include versioned API routes
app.include_router(api_router, prefix="/api/v1")
