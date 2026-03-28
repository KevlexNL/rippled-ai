"""Voice bridge FastAPI application.

Twilio <-> Gemini Live audio bridge for real-time voice interaction.
"""
import logging

from fastapi import FastAPI

from app.voice_bridge.twilio_handler import router as twilio_router

logger = logging.getLogger(__name__)

voice_app = FastAPI(
    title="Rippled Voice Bridge",
    description="Twilio <-> Gemini Live audio bridge service",
    version="0.1.0",
)

voice_app.include_router(twilio_router)
