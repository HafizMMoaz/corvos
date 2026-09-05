"""Voice Agent Service: orchestrates the speech-to-speech pipeline.

Connects STT (audio → text), the Corvos chat agent (text → response),
and TTS (response → audio) into a single service that accepts audio input
and returns audio output.

Usage::

    service = VoiceAgentService(workspace_id=1, thread_id=42)
    response = await service.process_voice(audio_bytes, voice_id="pNInz6obpgDQGcFmaJgB")
    # response.transcription  → what the user said
    # response.reply_text     → what the agent replied
    # response.reply_audio    → MP3 bytes of the spoken reply
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession

from .stt import SpeechToTextService, TranscriptionResult

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class VoiceAgentResponse:
    """The complete output of a voice agent turn."""

    transcription: str
    reply_text: str
    reply_audio: bytes
    reply_audio_content_type: str = "audio/mpeg"
    language: str | None = None
    duration_seconds: float | None = None
    metadata: dict = field(default_factory=dict)


class VoiceAgentService:
    """Full speech-to-speech pipeline for the Corvos voice agent.

    Each instance is bound to a workspace and optionally a chat thread,
    so conversational context is preserved across turns.
    """

    def __init__(
        self,
        *,
        workspace_id: int,
        user_id: str | None = None,
        thread_id: int | None = None,
        voice_id: str | None = None,
        tts_model: str | None = None,
        stt_language_hint: str | None = None,
    ) -> None:
        self._workspace_id = workspace_id
        self._user_id = user_id
        self._thread_id = thread_id
        self._voice_id = voice_id
        self._tts_model = tts_model
        self._stt_language_hint = stt_language_hint

    def _resolve_voice_id(self) -> str:
        """Return the ElevenLabs voice ID from args or config.

        Accepts both raw ElevenLabs voice IDs and catalog-prefixed IDs
        (``elevenlabs:<id>``); the prefix is stripped before calling the API.
        """
        if self._voice_id:
            return self._voice_id.removeprefix("elevenlabs:")
        from app.config import config as app_config

        return (app_config.ELEVENLABS_VOICE_ID or "pNInz6obpgDQGcFmaJgB").removeprefix(
            "elevenlabs:"
        )

    def _resolve_tts_model(self) -> str:
        """Return the ElevenLabs TTS model from args or config."""
        if self._tts_model:
            return self._tts_model
        from app.config import config as app_config

        return app_config.ELEVENLABS_MODEL or "eleven_multilingual_v2"

    async def process_voice(
        self,
        audio_data: bytes,
        *,
        content_type: str = "audio/mpeg",
        db_session: AsyncSession | None = None,
    ) -> VoiceAgentResponse:
        """Process a voice turn: STT → Chat Agent → TTS.

        Args:
            audio_data: Raw audio bytes from the user.
            content_type: MIME type of the audio.
            db_session: Optional database session (created if not provided).

        Returns:
            VoiceAgentResponse with transcription, reply text, and reply audio.
        """
        # ── Step 1: Speech-to-Text ──
        stt = SpeechToTextService()
        transcription = await stt.transcribe(
            audio_data,
            content_type=content_type,
            language_hint=self._stt_language_hint,
        )

        if not transcription.text.strip():
            # Nothing was said - return a short prompt
            return await self._synthesize_empty_response(transcription)

        logger.info(
            "Voice agent: transcribed %d chars from audio",
            len(transcription.text),
        )

        # ── Step 2: Chat Agent ──
        reply_text = await self._run_chat_agent(transcription.text, db_session)

        logger.info(
            "Voice agent: generated reply (%d chars)", len(reply_text)
        )

        # ── Step 3: Text-to-Speech ──
        reply_audio = await self._synthesize_speech(reply_text)

        return VoiceAgentResponse(
            transcription=transcription.text,
            reply_text=reply_text,
            reply_audio=reply_audio,
            reply_audio_content_type="audio/mpeg",
            language=transcription.language,
            duration_seconds=transcription.duration_seconds,
            metadata={
                "voice_id": self._resolve_voice_id(),
                "tts_model": self._resolve_tts_model(),
                "thread_id": self._thread_id,
            },
        )

    async def text_to_speech(
        self,
        text: str,
        *,
        voice_id: str | None = None,
    ) -> bytes:
        """Synthesise text to audio (TTS only, no STT or chat).

        Useful for generating audio from pre-existing text responses.
        """
        return await self._synthesize_speech(text, voice_id=voice_id)

    async def speech_to_text(
        self,
        audio_data: bytes,
        *,
        content_type: str = "audio/mpeg",
    ) -> TranscriptionResult:
        """Transcribe audio to text (STT only, no chat or TTS)."""
        stt = SpeechToTextService()
        return await stt.transcribe(
            audio_data,
            content_type=content_type,
            language_hint=self._stt_language_hint,
        )

    # ── Private helpers ──────────────────────────────────────────────

    async def _run_chat_agent(
        self, text: str, db_session: AsyncSession | None
    ) -> str:
        """Send text through the Corvos chat agent and extract the reply.

        This calls the multi-agent chat system to get a full agent response
        with tool usage, search, etc. For simpler use cases, a direct LLM
        call could be substituted.
        """
        from app.config import config as app_config

        api_key = app_config.ELEVENLABS_API_KEY

        # Use ElevenLabs Conversational AI agent if configured
        agent_id = app_config.ELEVENLABS_VOICE_AGENT_ID
        if agent_id:
            return await self._run_elevenlabs_conversational(text, agent_id, api_key)

        # Otherwise, use the Corvos chat agent via internal API
        return await self._run_corvos_agent(text, db_session)

    async def _run_elevenlabs_conversational(
        self, text: str, agent_id: str, api_key: str
    ) -> str:
        """Use ElevenLabs Conversational AI for voice-optimised responses."""
        import asyncio

        try:
            from elevenlabs import ElevenLabs
        except ImportError:
            logger.warning(
                "ElevenLabs SDK not available, falling back to Corvos agent"
            )
            return await self._run_corvos_agent(text, None)

        client = ElevenLabs(api_key=api_key)

        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.conversational_ai.agents.chat(
                    agent_id=agent_id,
                    conversation_id=None,  # New conversation each time
                    text=text,
                ),
            )
            # Extract the agent's reply text
            reply = getattr(result, "text", "") or getattr(result, "message", "")
            return str(reply).strip() or "I couldn't process that request."
        except Exception as exc:
            logger.error("ElevenLabs conversational AI failed: %s", exc)
            return await self._run_corvos_agent(text, None)

    async def _run_corvos_agent(
        self, text: str, db_session: AsyncSession | None
    ) -> str:
        """Send through the Corvos multi-agent chat system."""
        import asyncio

        try:
            from app.services.llm_service import get_agent_llm
            from langchain_core.messages import HumanMessage, SystemMessage

            # Get an LLM instance
            if db_session is None:
                from app.db import async_session_maker

                async with async_session_maker() as session:
                    llm = await get_agent_llm(session, self._workspace_id)
            else:
                llm = await get_agent_llm(db_session, self._workspace_id)

            if not llm:
                return (
                    "I'm sorry, no AI model is configured for this workspace. "
                    "Please ask an administrator to set up an LLM connection."
                )

            # Build a voice-optimised system prompt
            system_prompt = (
                "You are Corvos, a helpful AI research assistant. "
                "The user is speaking to you via voice, so keep your responses "
                "concise, conversational, and natural-sounding. "
                "Avoid markdown formatting, bullet points, or code blocks. "
                "Speak naturally as if in a conversation. "
                "Keep responses under 3 sentences unless the user asks for detail."
            )
            # Reply in the user's selected/conversational language when set.
            if self._stt_language_hint:
                system_prompt += (
                    f" IMPORTANT: Always reply in the language with BCP-47 code "
                    f"\"{self._stt_language_hint}\" (or the language the user "
                    f"speaks, if it differs). Do not switch languages unless asked."
                )

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=text),
            ]

            response = await llm.ainvoke(messages)
            return str(response.content).strip()

        except Exception as exc:
            logger.error("Corvos agent failed: %s", exc)
            return (
                "I'm having trouble processing that right now. "
                "Could you try again?"
            )

    async def _synthesize_speech(
        self, text: str, *, voice_id: str | None = None
    ) -> bytes:
        """Synthesise text to MP3 audio via ElevenLabs TTS."""
        from app.podcasts.tts.adapters.elevenlabs import ElevenLabsTextToSpeech
        from app.podcasts.tts.request import SynthesisRequest

        voice = voice_id or self._resolve_voice_id()
        model = self._resolve_tts_model()

        tts = ElevenLabsTextToSpeech(model=model)
        request = SynthesisRequest(
            text=text,
            voice=voice,
            language=self._stt_language_hint or "en",
        )

        audio = await tts.synthesize(request)
        return audio.data

    async def _synthesize_empty_response(
        self, transcription: TranscriptionResult
    ) -> VoiceAgentResponse:
        """Handle empty transcription with a prompt to speak."""
        prompt_text = "I didn't catch that. Could you say something?"
        audio = await self._synthesize_speech(prompt_text)

        return VoiceAgentResponse(
            transcription=transcription.text,
            reply_text=prompt_text,
            reply_audio=audio,
            reply_audio_content_type="audio/mpeg",
            language=transcription.language,
            metadata={
                "voice_id": self._resolve_voice_id(),
                "empty_input": True,
            },
        )
