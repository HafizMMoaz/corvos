"""Voice Agent API routes: speech-to-speech conversation endpoints.

Provides REST endpoints for voice interactions with the Corvos AI agent:
- POST /voice/agent - Full speech-to-speech turn (upload audio → get audio)
- POST /voice/tts - Text-to-speech only (text → audio)
- POST /voice/stt - Speech-to-text only (audio → text)
- GET  /voice/voices - List built-in catalog ElevenLabs voices
- GET  /voice/library - List the user's ElevenLabs voice library (accent voices)
- GET  /voice/languages - List supported languages for STT/TTS
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from app.auth.context import AuthContext
from app.users import get_auth_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])


# ── Request/Response schemas ─────────────────────────────────────────


class TextToSpeechRequest(BaseModel):
    text: str
    voice_id: str | None = None
    model: str | None = None


class TextToSpeechResponse(BaseModel):
    audio_content_type: str = "audio/mpeg"


class SpeechToTextResponse(BaseModel):
    text: str
    language: str | None = None
    duration_seconds: float | None = None


class VoiceAgentResponseSchema(BaseModel):
    transcription: str
    reply_text: str
    reply_audio_content_type: str = "audio/mpeg"
    language: str | None = None


class VoiceInfo(BaseModel):
    voice_id: str
    display_name: str
    gender: str
    language: str
    accent: str | None = None
    preview_url: str | None = None


class LibraryVoice(BaseModel):
    """A voice from the user's ElevenLabs voice library.

    Library voices carry accent labels (e.g. ``indian``, ``pakistani``,
    ``chinese``, ``american``) set by the ElevenLabs Voice Library, so users
    can pick an agent voice that matches their preferred accent.
    """

    voice_id: str
    name: str
    accent: str | None = None
    language: str | None = None
    gender: str | None = None
    age: str | None = None
    description: str | None = None
    preview_url: str | None = None
    category: str | None = None


class LanguageInfo(BaseModel):
    """A selectable conversation language (BCP-47 code + display names)."""

    code: str
    name: str
    native_name: str
    flag: str


# Curated language list: STT (Scribe) covers ~99 languages, the multilingual
# v2 TTS model covers 29. This list covers the languages both sides handle
# well plus the most-requested locales by our user base.
SUPPORTED_LANGUAGES: tuple[LanguageInfo, ...] = (
    LanguageInfo(code="en", name="English", native_name="English", flag="\U0001f1fa\U0001f1f8"),
    LanguageInfo(code="hi", name="Hindi", native_name="\u0939\u093f\u0928\u094d\u0926\u0940", flag="\U0001f1ee\U0001f1f3"),
    LanguageInfo(code="ur", name="Urdu", native_name="\u0627\u0631\u062f\u0648", flag="\U0001f1f5\U0001f1f0"),
    LanguageInfo(code="zh", name="Chinese", native_name="\u4e2d\u6587", flag="\U0001f1e8\U0001f1f3"),
    LanguageInfo(code="ar", name="Arabic", native_name="\u0627\u0644\u0639\u0631\u0628\u064a\u0629", flag="\U0001f1f8\U0001f1e6"),
    LanguageInfo(code="bn", name="Bengali", native_name="\u09ac\u09be\u0982\u09b2\u09be", flag="\U0001f1e7\U0001f1e9"),
    LanguageInfo(code="pa", name="Punjabi", native_name="\u0a2a\u0a70\u0a1c\u0a3e\u0a2c\u0a40", flag="\U0001f1f5\U0001f1f0"),
    LanguageInfo(code="ta", name="Tamil", native_name="\u0ba4\u0bae\u0bbf\u0bb4\u0bcd", flag="\U0001f1ee\U0001f1f3"),
    LanguageInfo(code="te", name="Telugu", native_name="\u0c24\u0c46\u0c32\u0c41\u0c17\u0c41", flag="\U0001f1ee\U0001f1f3"),
    LanguageInfo(code="mr", name="Marathi", native_name="\u092e\u0930\u093e\u0920\u0940", flag="\U0001f1ee\U0001f1f3"),
    LanguageInfo(code="gu", name="Gujarati", native_name="\u0a97\u0ac1\u0a9c\u0ab0\u0abe\u0aa4\u0ac0", flag="\U0001f1ee\U0001f1f3"),
    LanguageInfo(code="kn", name="Kannada", native_name="\u0c95\u0ca8\u0ccd\u0ca8\u0ca1", flag="\U0001f1ee\U0001f1f3"),
    LanguageInfo(code="ml", name="Malayalam", native_name="\u0d2e\u0d32\u0d2f\u0d3e\u0d33\u0d02", flag="\U0001f1ee\U0001f1f3"),
    LanguageInfo(code="es", name="Spanish", native_name="Espa\u00f1ol", flag="\U0001f1ea\U0001f1f8"),
    LanguageInfo(code="fr", name="French", native_name="Fran\u00e7ais", flag="\U0001f1eb\U0001f1f7"),
    LanguageInfo(code="de", name="German", native_name="Deutsch", flag="\U0001f1e9\U0001f1ea"),
    LanguageInfo(code="it", name="Italian", native_name="Italiano", flag="\U0001f1ee\U0001f1f9"),
    LanguageInfo(code="pt", name="Portuguese", native_name="Portugu\u00eas", flag="\U0001f1e7\U0001f1f7"),
    LanguageInfo(code="ru", name="Russian", native_name="\u0420\u0443\u0441\u0441\u043a\u0438\u0439", flag="\U0001f1f7\U0001f1fa"),
    LanguageInfo(code="ja", name="Japanese", native_name="\u65e5\u672c\u8a9e", flag="\U0001f1ef\U0001f1f5"),
    LanguageInfo(code="ko", name="Korean", native_name="\ud55c\uad6d\uc5b4", flag="\U0001f1f0\U0001f1f7"),
    LanguageInfo(code="tr", name="Turkish", native_name="T\u00fcrk\u00e7e", flag="\U0001f1f9\U0001f1f7"),
    LanguageInfo(code="id", name="Indonesian", native_name="Bahasa Indonesia", flag="\U0001f1ee\U0001f1e9"),
    LanguageInfo(code="nl", name="Dutch", native_name="Nederlands", flag="\U0001f1f3\U0001f1f1"),
    LanguageInfo(code="pl", name="Polish", native_name="Polski", flag="\U0001f1f5\U0001f1f1"),
    LanguageInfo(code="uk", name="Ukrainian", native_name="\u0423\u043a\u0440\u0430\u0457\u043d\u0441\u044c\u043a\u0430", flag="\U0001f1fa\U0001f1e6"),
    LanguageInfo(code="fa", name="Persian", native_name="\u0641\u0627\u0631\u0633\u06cc", flag="\U0001f1ee\U0001f1f7"),
    LanguageInfo(code="vi", name="Vietnamese", native_name="Ti\u1ebfng Vi\u1ec7t", flag="\U0001f1fb\U0001f1f3"),
    LanguageInfo(code="th", name="Thai", native_name="\u0e44\u0e17\u0e22", flag="\U0001f1f9\U0001f1ed"),
    LanguageInfo(code="sv", name="Swedish", native_name="Svenska", flag="\U0001f1f8\U0001f1ea"),
    LanguageInfo(code="fil", name="Filipino", native_name="Filipino", flag="\U0001f1f5\U0001f1ed"),
)


# ── Endpoints ────────────────────────────────────────────────────────


@router.post(
    "/agent",
    summary="Voice agent turn",
    description=(
        "Full speech-to-speech turn: upload audio, get transcribed text, "
        "agent reply text, and spoken reply audio back."
    ),
)
async def voice_agent_turn(
    audio: UploadFile = File(..., description="Audio file (mp3, wav, m4a, ogg)"),
    workspace_id: int = Form(..., description="Workspace ID"),
    thread_id: int | None = Form(None, description="Chat thread ID for context"),
    voice_id: str | None = Form(None, description="ElevenLabs voice ID"),
    language: str | None = Form(None, description="Language hint (BCP-47)"),
    auth: AuthContext = Depends(get_auth_context),
):
    """Process a full voice turn: STT → Chat Agent → TTS."""
    user = auth.user
    audio_data = await audio.read()
    if not audio_data:
        raise HTTPException(status_code=400, detail="No audio data received")

    content_type = audio.content_type or "audio/mpeg"

    from app.agents.voice_agent import VoiceAgentService

    service = VoiceAgentService(
        workspace_id=workspace_id,
        user_id=str(user.id) if user else None,
        thread_id=thread_id,
        voice_id=voice_id,
        stt_language_hint=language,
    )

    try:
        result = await service.process_voice(
            audio_data, content_type=content_type
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("Voice agent error: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Voice agent processing failed. Please try again.",
        )

    # Return audio with metadata headers for the client
    return Response(
        content=result.reply_audio,
        media_type="audio/mpeg",
        headers={
            "X-Voice-Transcription": _safe_header(result.transcription),
            "X-Voice-Reply-Text": _safe_header(result.reply_text),
            "X-Voice-Language": result.language or "",
            "Content-Disposition": 'attachment; filename="reply.mp3"',
        },
    )


@router.post(
    "/tts",
    summary="Text-to-speech",
    description="Synthesise text to speech audio via ElevenLabs.",
)
async def text_to_speech(
    request: TextToSpeechRequest,
    auth: AuthContext = Depends(get_auth_context),
):
    """Convert text to speech audio."""
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    from app.agents.voice_agent import VoiceAgentService

    service = VoiceAgentService(
        workspace_id=0,  # TTS doesn't need workspace context
        voice_id=request.voice_id,
        tts_model=request.model,
    )

    try:
        audio = await service.text_to_speech(request.text)
    except Exception as exc:
        logger.error("TTS failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Text-to-speech failed")

    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"Content-Disposition": 'attachment; filename="speech.mp3"'},
    )


@router.post(
    "/stt",
    summary="Speech-to-text",
    description="Transcribe audio to text via ElevenLabs Scribe or local Whisper.",
)
async def speech_to_text(
    audio: UploadFile = File(..., description="Audio file"),
    language: str | None = Form(None, description="Language hint"),
    auth: AuthContext = Depends(get_auth_context),
):
    """Transcribe audio to text."""
    audio_data = await audio.read()
    if not audio_data:
        raise HTTPException(status_code=400, detail="No audio data received")

    content_type = audio.content_type or "audio/mpeg"

    from app.agents.voice_agent import SpeechToTextService

    stt = SpeechToTextService()

    try:
        result = await stt.transcribe(
            audio_data,
            content_type=content_type,
            language_hint=language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("STT failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Speech-to-text failed")

    return SpeechToTextResponse(
        text=result.text,
        language=result.language,
        duration_seconds=result.duration_seconds,
    )


@router.get(
    "/voices",
    summary="List built-in ElevenLabs voices",
    description="List available ElevenLabs voices for the voice agent.",
)
async def list_voices(auth: AuthContext = Depends(get_auth_context)):
    """List all ElevenLabs voices available in the catalog."""
    from app.podcasts.voices import TtsProvider, get_voice_catalog

    catalog = get_voice_catalog()
    voices = catalog.for_provider(TtsProvider.ELEVENLABS)

    return [
        VoiceInfo(
            voice_id=v.voice_id,
            display_name=v.display_name,
            gender=v.gender.value,
            language=v.language,
            accent="american" if v.language == "*" else None,
            preview_url=f"/api/v1/podcasts/voices/{v.voice_id}/preview",
        )
        for v in voices
    ]


@router.get(
    "/library",
    summary="List ElevenLabs voice library",
    description=(
        "List voices from the account's ElevenLabs voice library, including "
        "community voices with accent labels (indian, pakistani, chinese, "
        "british, american, ...). These voices can be selected as the "
        "agent's speaking voice."
    ),
)
async def list_library_voices(auth: AuthContext = Depends(get_auth_context)):
    """List the ElevenLabs voice library for this deployment's API key."""
    import asyncio

    from app.config import config as app_config

    api_key = app_config.ELEVENLABS_API_KEY
    if not api_key:
        return []

    try:
        from elevenlabs import ElevenLabs
    except ImportError:
        return []

    client = ElevenLabs(api_key=api_key)

    def _fetch():
        return client.voices.get_all()

    try:
        result = await asyncio.get_event_loop().run_in_executor(None, _fetch)
    except Exception as exc:
        logger.error("Failed to list ElevenLabs library voices: %s", exc)
        raise HTTPException(
            status_code=502,
            detail="Could not fetch the ElevenLabs voice library.",
        )

    voices = getattr(result, "voices", None) or []
    library = []
    for voice in voices:
        labels = getattr(voice, "labels", None) or {}
        library.append(
            LibraryVoice(
                voice_id=voice.voice_id,
                name=voice.name,
                accent=labels.get("accent"),
                language=labels.get("language"),
                gender=labels.get("gender"),
                age=labels.get("age"),
                description=labels.get("description"),
                preview_url=getattr(voice, "preview_url", None),
                category=getattr(voice, "category", None),
            )
        )
    return library


@router.get(
    "/languages",
    summary="List supported voice languages",
    description="Languages supported by the voice agent for STT and TTS.",
)
async def list_languages(auth: AuthContext = Depends(get_auth_context)):
    """List the curated set of supported conversation languages."""
    return list(SUPPORTED_LANGUAGES)


# ── Helpers ──────────────────────────────────────────────────────────


def _safe_header(value: str, max_len: int = 4096) -> str:
    """Truncate a header value to stay within HTTP header size limits."""
    value = value.replace("\n", " ").replace("\r", "")
    return value[:max_len] if len(value) > max_len else value
