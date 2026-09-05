"""ElevenLabs adapter: high-quality neural TTS via the ElevenLabs REST API.

ElevenLabs offers multilingual voices with low latency streaming synthesis.
This adapter uses the ``elevenlabs`` SDK for synthesis, returning MP3-encoded
bytes.  The adapter lazily imports the SDK so the rest of the TTS layer works
even when the optional dependency is not installed.
"""

from __future__ import annotations

from ..audio import SynthesizedAudio
from ..errors import TextToSpeechError
from ..port import TextToSpeech
from ..request import SynthesisRequest

_CONTAINER = "mp3"

# ElevenLabs models
DEFAULT_MODEL = "eleven_multilingual_v2"

# Mapping of BCP-47 primary subtag to ElevenLabs language name hint.
# ElevenLabs multilingual models auto-detect language, but the hint helps
# with pronunciation and prosody for shorter segments.
_LANG_HINTS = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "hi": "Hindi",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "pt": "Portuguese",
    "zh": "Chinese",
    "ar": "Arabic",
    "nl": "Dutch",
    "pl": "Polish",
    "ru": "Russian",
    "sv": "Swedish",
    "tr": "Turkish",
}


class ElevenLabsTextToSpeech(TextToSpeech):
    """Synthesises segments through the ElevenLabs API.

    Requires ``ELEVENLABS_API_KEY`` in the environment (or passed explicitly).
    The model defaults to ``eleven_multilingual_v2`` for the best quality and
    language coverage; override via ``model`` for turbo or monolingual use.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._client = None  # Lazy-initialised

    @property
    def container(self) -> str:
        return _CONTAINER

    def _get_client(self):
        """Lazily build the ElevenLabs client (heavy import + auth)."""
        if self._client is not None:
            return self._client

        try:
            from elevenlabs import ElevenLabs
        except ImportError as exc:
            raise TextToSpeechError(
                "The 'elevenlabs' package is required for ElevenLabs TTS. "
                "Install it with: pip install elevenlabs"
            ) from exc

        api_key = self._api_key
        if not api_key:
            from app.config import config as app_config

            api_key = app_config.ELEVENLABS_API_KEY

        if not api_key:
            raise TextToSpeechError(
                "ElevenLabs API key is not configured. "
                "Set ELEVENLABS_API_KEY in your environment."
            )

        self._client = ElevenLabs(api_key=api_key)
        return self._client

    async def synthesize(self, request: SynthesisRequest) -> SynthesizedAudio:
        import asyncio

        if not isinstance(request.voice, str):
            raise TextToSpeechError(
                "ElevenLabs voices are identified by string voice_id, "
                "not a mapping."
            )

        client = self._get_client()

        try:
            # ElevenLabs SDK is synchronous; run in executor to avoid blocking
            audio_data = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self._synthesize_sync(client, request),
            )
        except TextToSpeechError:
            raise
        except Exception as exc:
            raise TextToSpeechError(
                f"ElevenLabs synthesis failed: {exc}"
            ) from exc

        if not audio_data:
            raise TextToSpeechError("ElevenLabs returned no audio")

        return SynthesizedAudio(
            data=audio_data,
            container=_CONTAINER,
        )

    def _synthesize_sync(self, client, request: SynthesisRequest) -> bytes:
        """Run the actual ElevenLabs API call (called from executor)."""
        kwargs = {
            "text": request.text,
            "voice": request.voice,
            "model_id": self._model,
        }

        # Add language hint for multilingual model
        lang_primary = request.language.split("-", 1)[0].strip().lower()
        if self._model == "eleven_multilingual_v2" and lang_primary in _LANG_HINTS:
            kwargs["language_code"] = _get_elevenlabs_lang_code(lang_primary)

        response = client.text_to_speech.convert(**kwargs)

        # The SDK returns bytes directly from convert()
        if isinstance(response, bytes):
            return response

        # Some SDK versions return an iterator of chunks
        chunks = []
        for chunk in response:
            if isinstance(chunk, bytes):
                chunks.append(chunk)
            elif hasattr(chunk, "audio"):
                import base64

                chunks.append(base64.b64decode(chunk.audio))

        if not chunks:
            raise TextToSpeechError("ElevenLabs returned empty audio stream")

        return b"".join(chunks)


def _get_elevenlabs_lang_code(primary_tag: str) -> str:
    """Map a BCP-47 primary subtag to an ElevenLabs language code.

    ElevenLabs uses ISO 639-1 codes for the multilingual model.
    """
    return primary_tag  # ElevenLabs accepts ISO 639-1 directly
