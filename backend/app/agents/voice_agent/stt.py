"""Speech-to-Text service: transcribe audio to text.

Supports two backends:
- **ElevenLabs Scribe**: High-accuracy cloud STT via the ElevenLabs API
- **faster-whisper**: Local self-hosted STT (already a dependency)

The backend is selected by ``ELEVENLABS_STT_MODEL`` config:
- ``"scribe_v1"`` → ElevenLabs cloud (default when ELEVENLABS_API_KEY is set)
- ``"local/whisper"`` → faster-whisper local model
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TranscriptionResult:
    """The output of a speech-to-text transcription."""

    text: str
    language: str | None = None
    duration_seconds: float | None = None


class SpeechToTextService:
    """Transcribes audio bytes to text using the configured STT backend."""

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model

    def _resolve_config(self) -> tuple[str, str]:
        """Return (api_key, model) from explicit args or config singleton."""
        from app.config import config as app_config

        api_key = self._api_key or app_config.ELEVENLABS_API_KEY
        model = self._model or app_config.ELEVENLABS_STT_MODEL or "scribe_v1"
        return api_key, model

    async def transcribe(
        self,
        audio_data: bytes,
        *,
        content_type: str = "audio/mpeg",
        language_hint: str | None = None,
    ) -> TranscriptionResult:
        """Transcribe audio bytes to text.

        Args:
            audio_data: Raw audio file bytes (mp3, wav, m4a, ogg, etc.)
            content_type: MIME type of the audio data.
            language_hint: Optional BCP-47 language hint for better accuracy.

        Returns:
            TranscriptionResult with the transcribed text.

        Raises:
            ValueError: If no STT backend is configured or audio is empty.
        """
        if not audio_data:
            raise ValueError("No audio data provided for transcription")

        api_key, model = self._resolve_config()

        if model.startswith("local/"):
            return await self._transcribe_local(audio_data, language_hint)

        return await self._transcribe_elevenlabs(
            audio_data, api_key, model, content_type, language_hint
        )

    async def _transcribe_elevenlabs(
        self,
        audio_data: bytes,
        api_key: str,
        model: str,
        content_type: str,
        language_hint: str | None,
    ) -> TranscriptionResult:
        """Transcribe via ElevenLabs Scribe API."""
        import asyncio

        if not api_key:
            raise ValueError(
                "ElevenLabs API key is not configured. "
                "Set ELEVENLABS_API_KEY in your environment."
            )

        try:
            from elevenlabs import ElevenLabs
        except ImportError as exc:
            raise ValueError(
                "The 'elevenlabs' package is required. "
                "Install it with: pip install elevenlabs"
            ) from exc

        client = ElevenLabs(api_key=api_key)

        # ElevenLabs SDK expects a file-like object
        audio_file = io.BytesIO(audio_data)
        audio_file.name = f"audio.{_extension_from_mime(content_type)}"

        try:
            result = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: client.speech_to_text.convert(
                    file=audio_file,
                    model_id=model,
                    **(
                        {"language_code": language_hint}
                        if language_hint
                        else {}
                    ),
                ),
            )
        except Exception as exc:
            logger.error("ElevenLabs STT failed: %s", exc)
            raise ValueError(f"Speech-to-text failed: {exc}") from exc

        text = getattr(result, "text", "") or ""
        language = getattr(result, "language_code", None)

        return TranscriptionResult(
            text=text.strip(),
            language=language,
        )

    async def _transcribe_local(
        self,
        audio_data: bytes,
        language_hint: str | None,
    ) -> TranscriptionResult:
        """Transcribe via local faster-whisper model."""
        import asyncio
        import tempfile
        from pathlib import Path

        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise ValueError(
                "faster-whisper is required for local STT. "
                "Install it with: pip install faster-whisper"
            ) from exc

        # Write audio to a temp file (faster-whisper needs a file path)
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        try:
            tmp.write(audio_data)
            tmp.flush()
            tmp_path = tmp.name
        finally:
            tmp.close()

        try:

            def _run_whisper() -> tuple[str, str | None, float]:
                model = WhisperModel("base", compute_type="int8")
                segments, info = model.transcribe(
                    tmp_path,
                    language=language_hint,
                    beam_size=5,
                )
                text = " ".join(seg.text for seg in segments).strip()
                return text, info.language, info.duration

            text, language, duration = await asyncio.get_event_loop().run_in_executor(
                None, _run_whisper
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

        return TranscriptionResult(
            text=text,
            language=language,
            duration_seconds=duration,
        )


def _extension_from_mime(content_type: str) -> str:
    """Map a MIME type to a file extension for the ElevenLabs SDK."""
    mapping = {
        "audio/mpeg": "mp3",
        "audio/mp3": "mp3",
        "audio/wav": "wav",
        "audio/wave": "wav",
        "audio/x-wav": "wav",
        "audio/ogg": "ogg",
        "audio/m4a": "m4a",
        "audio/mp4": "m4a",
        "audio/webm": "webm",
        "audio/flac": "flac",
    }
    return mapping.get(content_type.lower(), "mp3")
