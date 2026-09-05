"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { type VoiceAgentResult, voiceApiService } from "@/lib/apis/voice-api.service";

export type { VoiceAgentResult };

export type VoiceState =
	| "idle"
	| "requesting_mic"
	| "recording"
	| "processing"
	| "playing"
	| "error";

export interface UseVoiceRecordingOptions {
	workspaceId: number;
	threadId?: number | null;
	voiceId?: string;
	/** BCP-47 language hint for STT accuracy (null = auto-detect). */
	language?: string | null;
	onResult?: (result: VoiceAgentResult) => void;
}

export interface UseVoiceRecordingReturn {
	voiceState: VoiceState;
	recordingSeconds: number;
	startRecording: () => Promise<boolean>;
	stopRecording: () => void;
	cancelRecording: () => void;
	stopPlayback: () => void;
}

const AUDIO_TYPES = [
	"audio/webm;codecs=opus",
	"audio/webm",
	"audio/ogg;codecs=opus",
	"audio/mp4",
] as const;

function pickAudioType(): string {
	for (const t of AUDIO_TYPES) {
		if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(t)) {
			return t;
		}
	}
	return "";
}

export function useVoiceRecording(opts: UseVoiceRecordingOptions): UseVoiceRecordingReturn {
	const [voiceState, setVoiceState] = useState<VoiceState>("idle");
	const [recordingSeconds, setRecordingSeconds] = useState(0);

	const recorderRef = useRef<MediaRecorder | null>(null);
	const chunksRef = useRef<Blob[]>([]);
	const streamRef = useRef<MediaStream | null>(null);
	const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
	const audioRef = useRef<HTMLAudioElement | null>(null);
	const abortRef = useRef<AbortController | null>(null);
	const cancelledRef = useRef(false);
	const optsRef = useRef(opts);
	optsRef.current = opts;

	useEffect(() => {
		return () => {
			if (timerRef.current) clearInterval(timerRef.current);
			const s = streamRef.current;
			if (s) for (const t of s.getTracks()) t.stop();
			const a = audioRef.current;
			if (a) {
				a.pause();
				a.currentTime = 0;
			}
			if (abortRef.current) abortRef.current.abort();
		};
	}, []);

	const stopRecordingInternal = useCallback(() => {
		if (timerRef.current) {
			clearInterval(timerRef.current);
			timerRef.current = null;
		}
		const recorder = recorderRef.current;
		if (recorder && recorder.state !== "inactive") recorder.stop();
		const stream = streamRef.current;
		if (stream) {
			for (const track of stream.getTracks()) track.stop();
			streamRef.current = null;
		}
		recorderRef.current = null;
	}, []);

	const processRecording = useCallback(async (audioBlob: Blob) => {
		setVoiceState("processing");
		const controller = new AbortController();
		abortRef.current = controller;
		try {
			const result = await voiceApiService.sendVoiceMessage(
				audioBlob,
				optsRef.current.workspaceId,
				{
					threadId: optsRef.current.threadId,
					voiceId: optsRef.current.voiceId,
					language: optsRef.current.language ?? undefined,
					signal: controller.signal,
				}
			);
			if (controller.signal.aborted) {
				setVoiceState("idle");
				return;
			}
			optsRef.current.onResult?.(result);
			playAudio(result.audio);
		} catch (err) {
			if (controller.signal.aborted) {
				setVoiceState("idle");
				return;
			}
			console.error("Voice agent error:", err);
			toast.error(err instanceof Error ? err.message : "Voice agent failed.");
			setVoiceState("idle");
		} finally {
			abortRef.current = null;
		}
	}, []);

	const playAudio = useCallback((blob: Blob) => {
		const url = URL.createObjectURL(blob);
		const audio = new Audio(url);
		audioRef.current = audio;
		audio.onended = () => {
			URL.revokeObjectURL(url);
			audioRef.current = null;
			setVoiceState("idle");
		};
		audio.onerror = () => {
			URL.revokeObjectURL(url);
			audioRef.current = null;
			setVoiceState("idle");
		};
		audio.play().then(
			() => setVoiceState("playing"),
			() => {
				URL.revokeObjectURL(url);
				audioRef.current = null;
				setVoiceState("idle");
			}
		);
	}, []);

	const startRecording = useCallback(async (): Promise<boolean> => {
		if (voiceState !== "idle") return false;
		setVoiceState("requesting_mic");
		cancelledRef.current = false;

		let stream: MediaStream;
		try {
			stream = await navigator.mediaDevices.getUserMedia({
				audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
			});
		} catch (err) {
			setVoiceState("idle");
			toast.error(
				err instanceof DOMException && err.name === "NotAllowedError"
					? "Microphone access denied. Enable it in browser settings."
					: "Could not access microphone."
			);
			return false;
		}

		streamRef.current = stream;
		const mimeType = pickAudioType();
		const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
		recorderRef.current = recorder;
		chunksRef.current = [];

		recorder.ondataavailable = (e: BlobEvent) => {
			if (e.data.size > 0) chunksRef.current.push(e.data);
		};
		recorder.onstop = () => {
			const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
			chunksRef.current = [];
			if (!cancelledRef.current) void processRecording(blob);
		};

		recorder.start(250);
		setVoiceState("recording");
		setRecordingSeconds(0);

		const startedAt = Date.now();
		timerRef.current = setInterval(() => {
			setRecordingSeconds(Math.floor((Date.now() - startedAt) / 1000));
		}, 500);

		return true;
	}, [voiceState, processRecording]);

	const stopRecording = useCallback(() => {
		cancelledRef.current = false;
		stopRecordingInternal();
	}, [stopRecordingInternal]);

	const cancelRecording = useCallback(() => {
		cancelledRef.current = true;
		stopRecordingInternal();
		setVoiceState("idle");
		setRecordingSeconds(0);
	}, [stopRecordingInternal]);

	const stopPlayback = useCallback(() => {
		const audio = audioRef.current;
		if (audio) {
			audio.pause();
			audio.currentTime = 0;
			audioRef.current = null;
		}
		if (abortRef.current) {
			abortRef.current.abort();
			abortRef.current = null;
		}
		setVoiceState("idle");
	}, []);

	return {
		voiceState,
		recordingSeconds,
		startRecording,
		stopRecording,
		cancelRecording,
		stopPlayback,
	};
}
