import { getDesktopAccessToken } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";
import { getClientPlatform } from "../agent-filesystem";
import { handleUnauthorized, refreshSession } from "../auth-utils";
import { baseApiService } from "./base-api.service";

export interface VoiceInfo {
	voice_id: string;
	display_name: string;
	gender: string;
	language: string;
	accent: string | null;
	preview_url: string | null;
}

export interface LibraryVoice {
	voice_id: string;
	name: string;
	accent: string | null;
	language: string | null;
	gender: string | null;
	age: string | null;
	description: string | null;
	preview_url: string | null;
	category: string | null;
}

export interface LanguageInfo {
	code: string;
	name: string;
	native_name: string;
	flag: string;
}

export interface VoiceAgentResult {
	/** Audio blob of the spoken reply (MP3). */
	audio: Blob;
	/** What the user said (transcribed from uploaded audio). */
	transcription: string;
	/** What the agent replied in text. */
	replyText: string;
	/** Detected language of the user's speech. */
	language: string;
}

class VoiceApiService {
	/**
	 * Full speech-to-speech turn. Uploads audio, receives an audio reply
	 * with metadata in response headers (X-Voice-Transcription, etc.).
	 *
	 * Uses raw fetch because baseApiService doesn't expose a
	 * multipart-POST → Blob path that preserves response headers.
	 */
	async sendVoiceMessage(
		audioBlob: Blob,
		workspaceId: number,
		opts?: {
			threadId?: number | null;
			voiceId?: string;
			language?: string;
			signal?: AbortSignal;
		}
	): Promise<VoiceAgentResult> {
		const formData = new FormData();
		formData.append("audio", audioBlob, "recording.webm");
		formData.append("workspace_id", String(workspaceId));
		if (opts?.threadId != null) {
			formData.append("thread_id", String(opts.threadId));
		}
		if (opts?.voiceId) {
			formData.append("voice_id", opts.voiceId);
		}
		if (opts?.language) {
			formData.append("language", opts.language);
		}

		const url = buildBackendUrl("/api/v1/voice/agent");
		const headers = await this._authHeaders();

		const response = await fetch(url, {
			method: "POST",
			headers,
			body: formData,
			signal: opts?.signal,
			credentials: "include",
		});

		if (response.status === 401) {
			const refreshed = await refreshSession();
			if (refreshed) {
				const retryHeaders = await this._authHeaders();
				const retry = await fetch(url, {
					method: "POST",
					headers: retryHeaders,
					body: formData,
					signal: opts?.signal,
					credentials: "include",
				});
				if (!retry.ok) throw new Error(`Voice agent failed: ${retry.status}`);
				return this._parseVoiceResponse(retry);
			}
			handleUnauthorized();
			throw new Error("Authentication required");
		}

		if (!response.ok) {
			const body = await response.text().catch(() => "");
			throw new Error(`Voice agent failed (${response.status}): ${body}`);
		}

		return this._parseVoiceResponse(response);
	}

	/**
	 * Transcribe audio to text without generating an agent reply.
	 */
	async transcribe(audioBlob: Blob, language?: string) {
		const formData = new FormData();
		formData.append("audio", audioBlob, "recording.webm");
		if (language) formData.append("language", language);

		return baseApiService.postFormData<{
			text: string;
			language: string | null;
			duration_seconds: number | null;
		}>(`/api/v1/voice/stt`, undefined, { body: formData });
	}

	/**
	 * Synthesise text to speech audio (returns an audio Blob).
	 */
	async synthesize(text: string, voiceId?: string, model?: string): Promise<Blob> {
		const url = buildBackendUrl("/api/v1/voice/tts");
		const headers = await this._authHeaders();
		headers["Content-Type"] = "application/json";

		const response = await fetch(url, {
			method: "POST",
			headers,
			body: JSON.stringify({ text, voice_id: voiceId, model }),
			credentials: "include",
		});

		if (!response.ok) throw new Error(`TTS failed: ${response.status}`);
		return response.blob();
	}

	/**
	 * List available ElevenLabs voices.
	 */
	async listVoices(): Promise<VoiceInfo[]> {
		return baseApiService.get<VoiceInfo[]>("/api/v1/voice/voices");
	}

	/**
	 * List the ElevenLabs voice library (community voices with accent labels
	 * like indian, pakistani, chinese, british, ...).
	 */
	async listLibraryVoices(): Promise<LibraryVoice[]> {
		return baseApiService.get<LibraryVoice[]>("/api/v1/voice/library");
	}

	/**
	 * List supported conversation languages (BCP-47 codes).
	 */
	async listLanguages(): Promise<LanguageInfo[]> {
		return baseApiService.get<LanguageInfo[]>("/api/v1/voice/languages");
	}

	/**
	 * Synthesize a short voice sample for preview.
	 */
	async previewVoice(voiceId: string): Promise<Blob> {
		return this.synthesize("Hello! This is how I sound.", voiceId);
	}

	// ── Private helpers ───────────────────────────────────────────

	private async _authHeaders(): Promise<Record<string, string>> {
		const isDesktop = typeof window !== "undefined" && !!window.electronAPI;
		const token = isDesktop ? await getDesktopAccessToken() : "";
		return {
			...(token ? { Authorization: `Bearer ${token}` } : {}),
			"X-Corvos-Client-Platform": typeof window === "undefined" ? "web" : getClientPlatform(),
		};
	}

	private async _parseVoiceResponse(response: Response): Promise<VoiceAgentResult> {
		const audio = await response.blob();
		return {
			audio,
			transcription: response.headers.get("X-Voice-Transcription") ?? "",
			replyText: response.headers.get("X-Voice-Reply-Text") ?? "",
			language: response.headers.get("X-Voice-Language") ?? "",
		};
	}
}

export const voiceApiService = new VoiceApiService();
