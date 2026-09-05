"""Voice Agent: speech-to-speech conversations with the Corvos AI agent.

This module implements the full voice pipeline:
  1. Speech-to-Text (STT): Transcribe user audio via ElevenLabs Scribe or faster-whisper
  2. Chat Agent: Process the transcribed text through the LangGraph multi-agent system
  3. Text-to-Speech (TTS): Synthesise the agent's response via ElevenLabs

Supports both request/response (upload audio, get audio back) and streaming
(WebSocket-based real-time voice conversation) modes.
"""

from __future__ import annotations

from .service import VoiceAgentService, VoiceAgentResponse
from .stt import SpeechToTextService, TranscriptionResult

__all__ = [
    "SpeechToTextService",
    "TranscriptionResult",
    "VoiceAgentResponse",
    "VoiceAgentService",
]
