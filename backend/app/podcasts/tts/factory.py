"""Resolve the configured :class:`TextToSpeech` as a process-wide singleton."""

from __future__ import annotations

from functools import lru_cache

from .port import TextToSpeech

# Sentinel model string that selects the local Kokoro pipeline; anything else is
# treated as a LiteLLM-hosted model (``openai/...``, ``vertex_ai/...``, etc.).
KOKORO_SERVICE = "local/kokoro"

# ElevenLabs service prefix; ``elevenlabs/...`` selects the ElevenLabs adapter
# with an optional model suffix (e.g. ``elevenlabs/eleven_turbo_v2_5``).
ELEVENLABS_PREFIX = "elevenlabs"


@lru_cache(maxsize=1)
def get_text_to_speech() -> TextToSpeech:
    """Build the provider selected by ``TTS_SERVICE`` (adapters lazy-imported).

    Cached because the Kokoro adapter holds loaded pipelines that must be reused
    across segments and requests rather than rebuilt per call.
    """
    from app.config import config as app_config

    service = app_config.TTS_SERVICE
    if not service:
        raise ValueError("TTS_SERVICE is not configured")

    if service == KOKORO_SERVICE:
        from .adapters.kokoro import KokoroTextToSpeech

        return KokoroTextToSpeech()

    # ElevenLabs: ``elevenlabs`` or ``elevenlabs/<model>``
    prefix = service.split("/", 1)[0].strip().lower()
    if prefix == ELEVENLABS_PREFIX:
        from .adapters.elevenlabs import ElevenLabsTextToSpeech

        # Allow ``elevenlabs/eleven_turbo_v2_5`` to override the model
        parts = service.split("/", 1)
        model = parts[1] if len(parts) > 1 and parts[1] else "eleven_multilingual_v2"
        return ElevenLabsTextToSpeech(
            api_key=app_config.ELEVENLABS_API_KEY,
            model=model,
        )

    from .adapters.litellm import LiteLlmTextToSpeech

    return LiteLlmTextToSpeech(
        model=service,
        api_base=app_config.TTS_SERVICE_API_BASE,
        api_key=app_config.TTS_SERVICE_API_KEY,
    )
