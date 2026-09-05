"""Video parser: extract audio track via FFmpeg, then transcribe.

Video files (.avi, .mkv, .mov, etc.) are not directly accepted by most
speech-to-text APIs.  This module extracts the audio track as a 16 kHz
mono WAV file using *python-ffmpeg* (which relies on the FFmpeg binary
bundled by *static-ffmpeg*) and then delegates to the existing audio
transcription pipeline.

The caller (EtlPipelineService) treats the result identically to audio -
the markdown transcript is chunked, embedded, and indexed by the same
indexing pipeline that handles all other document types.
"""

import asyncio
import logging
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


async def extract_and_transcribe_video(file_path: str, filename: str) -> str:
    """Extract the audio track from a video and transcribe it.

    1. Run FFmpeg to extract audio → 16 kHz mono WAV (off the event loop).
    2. Pass the WAV to ``transcribe_audio`` which routes through either
       the external STT API (OpenAI Whisper via Litellm) or the local
       faster-whisper model.
    3. Clean up the temporary WAV file regardless of outcome.
    """
    from app.etl_pipeline.parsers.audio import transcribe_audio

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        audio_path = tmp.name

    try:
        import ffmpeg  # python-ffmpeg

        logger.info("Extracting audio from video %s", filename)

        # Extract first audio stream as 16 kHz mono WAV (optimal for STT).
        # -vn       → no video stream
        # -ac 1     → mono
        # -ar 16000 → 16 kHz sample rate
        process = (
            ffmpeg
            .input(file_path)
            .output(audio_path, vn=None, acodec="pcm_s16le", ar=16000, ac=1)
            .overwrite_output()
        )

        # Run FFmpeg in a thread to avoid blocking the event loop.
        # static-ffmpeg ensures the binary is available without system install.
        try:
            await asyncio.to_thread(
                process.run,
                capture_stdout=True,
                capture_stderr=True,
                quiet=True,
            )
        except ffmpeg.Error as exc:
            stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
            raise RuntimeError(
                f"FFmpeg failed to extract audio from {filename}: {stderr}"
            ) from exc

        # Verify the extracted audio file exists and is non-empty.
        audio_file = Path(audio_path)
        if not audio_file.exists() or audio_file.stat().st_size == 0:
            raise RuntimeError(
                f"FFmpeg produced no audio output for {filename}"
            )

        logger.info(
            "Extracted audio from %s (%.1f MB)",
            filename,
            audio_file.stat().st_size / (1024 * 1024),
        )

        # Delegate to the existing audio transcription pipeline.
        text = await transcribe_audio(audio_path, filename)
        return f"# Video Transcript of {filename}\n\n{text}"

    finally:
        # Always clean up the temporary audio file.
        try:
            Path(audio_path).unlink(missing_ok=True)
        except OSError:
            pass
