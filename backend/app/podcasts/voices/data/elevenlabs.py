"""ElevenLabs TTS voices: premium neural voices with multilingual support.

ElevenLabs voices support 29+ languages via the ``eleven_multilingual_v2`` model.
Voices tagged :data:`ANY_LANGUAGE` work across all supported languages; specific
locale voices are tagged with their primary language for catalog filtering.

Voice IDs are ElevenLabs' stable voice IDs from their API/library.
"""

from __future__ import annotations

from ..provider import TtsProvider
from ..voice import ANY_LANGUAGE, CatalogVoice, VoiceGender


def _voice(
    voice_id: str,
    name: str,
    display: str,
    gender: VoiceGender,
    language: str = ANY_LANGUAGE,
) -> CatalogVoice:
    return CatalogVoice(
        voice_id=f"elevenlabs:{voice_id}",
        provider=TtsProvider.ELEVENLABS,
        language=language,
        display_name=display,
        gender=gender,
        native_ref=voice_id,
    )


ELEVENLABS_VOICES: tuple[CatalogVoice, ...] = (
    # ── Premium multilingual voices (work across all languages) ──
    _voice(
        "pNInz6obpgDQGcFmaJgB",
        "Adam",
        "Adam",
        VoiceGender.MALE,
    ),
    _voice(
        "21m00Tcm4TlvDq8ikWAM",
        "Rachel",
        "Rachel",
        VoiceGender.FEMALE,
    ),
    _voice(
        "AZnzlk1XvdvUeBnXmlld",
        "Domi",
        "Domi",
        VoiceGender.FEMALE,
    ),
    _voice(
        "EXAVITQu4vr4xnSDxMaL",
        "Bella",
        "Bella",
        VoiceGender.FEMALE,
    ),
    _voice(
        "ErXwobaYiN019PkySvjV",
        "Antoni",
        "Antoni",
        VoiceGender.MALE,
    ),
    _voice(
        "MF3mGyEYCl7XYWbV9V6O",
        "Elli",
        "Elli",
        VoiceGender.FEMALE,
    ),
    _voice(
        "TxGEqnHWrfWFTfGW9XjX",
        "Josh",
        "Josh",
        VoiceGender.MALE,
    ),
    _voice(
        "VR6AewLTigWG4xSOukaG",
        "Arnold",
        "Arnold",
        VoiceGender.MALE,
    ),
    _voice(
        "onwK4e9ZLuTAKqWW03F9",
        "Daniel",
        "Daniel",
        VoiceGender.MALE,
    ),
    _voice(
        "yoZ06aMxZJJ28mfd3POQ",
        "Sam",
        "Sam",
        VoiceGender.MALE,
    ),
    # ── English-optimised voices ──
    _voice(
        "IKne3meq5aSn9XLyUdCD",
        "Charlie",
        "Charlie",
        VoiceGender.MALE,
        "en",
    ),
    _voice(
        "XrExE9yKIg1WjnnlVkGX",
        "Matilda",
        "Matilda",
        VoiceGender.FEMALE,
        "en",
    ),
    _voice(
        "SOYHLrjzK2X1ezoPC6cr",
        "Harry",
        "Harry",
        VoiceGender.MALE,
        "en",
    ),
    _voice(
        "jBpfuIE2acCO8z3wKNLl",
        "Gigi",
        "Gigi",
        VoiceGender.FEMALE,
        "en",
    ),
    _voice(
        "a4Xx2Jl7gclBm8jVasfR",
        "James",
        "James",
        VoiceGender.MALE,
        "en",
    ),
)
