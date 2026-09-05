"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import { type VoiceAgentResult, voiceApiService } from "@/lib/apis/voice-api.service";

export type { VoiceAgentResult };

// ── Call & turn states ─────────────────────────────────────────────────

export type CallState = "idle" | "connecting" | "active" | "ended";
export type TurnState =
	| "listening" // mic open, waiting for user to speak
	| "speaking" // user is talking (VAD detected voice)
	| "processing" // audio sent to backend, awaiting reply
	| "agent_speaking" // agent's audio reply is playing
	| "paused"; // muted or error, not listening

// ── Tuning ─────────────────────────────────────────────────────────────

/** Volume below this (0-1) counts as silence. */
const SILENCE_THRESHOLD = 0.015;
/** Seconds of continuous silence before we auto-send. */
const SILENCE_DURATION = 1.5;
/** Minimum recording length (ms) to avoid sending empty clips. */
const MIN_RECORDING_MS = 400;
/** VAD polling interval (ms). */
const VAD_INTERVAL_MS = 60;

// ── Audio MIME type ────────────────────────────────────────────────────

const AUDIO_TYPES = [
	"audio/webm;codecs=opus",
	"audio/webm",
	"audio/ogg;codecs=opus",
	"audio/mp4",
] as const;

function pickAudioType(): string {
	for (const t of AUDIO_TYPES) {
		if (typeof MediaRecorder !== "undefined" && MediaRecorder.isTypeSupported(t)) return t;
	}
	return "";
}

// ── Options & return type ──────────────────────────────────────────────

export interface UseVoiceCallOptions {
	workspaceId: number;
	threadId?: number | null;
	voiceId?: string;
	/** BCP-47 language hint for STT accuracy (null = auto-detect). */
	language?: string | null;
	/** Called on each completed turn (transcription + reply). */
	onTurnResult?: (result: VoiceAgentResult) => void;
}

export interface UseVoiceCallReturn {
	callState: CallState;
	turnState: TurnState;
	/** Total call duration in seconds. */
	callSeconds: number;
	/** Seconds of the current recording turn. */
	turnSeconds: number;
	/** Whether the mic is muted. */
	isMuted: boolean;
	/** Start a continuous voice call. */
	startCall: () => Promise<void>;
	/** End the call and clean up. */
	endCall: () => void;
	/** Toggle mute (mic stays open but audio is not sent). */
	toggleMute: () => void;
	/** Force-send the current recording (skip silence wait). */
	sendNow: () => void;
}

// ── Hook ───────────────────────────────────────────────────────────────

export function useVoiceCall(opts: UseVoiceCallOptions): UseVoiceCallReturn {
	const [callState, setCallState] = useState<CallState>("idle");
	const [turnState, setTurnState] = useState<TurnState>("listening");
	const [callSeconds, setCallSeconds] = useState(0);
	const [turnSeconds, setTurnSeconds] = useState(0);
	const [isMuted, setIsMuted] = useState(false);

	const optsRef = useRef(opts);
	optsRef.current = opts;

	// Persistent refs across turns
	const streamRef = useRef<MediaStream | null>(null);
	const audioCtxRef = useRef<AudioContext | null>(null);
	const analyserRef = useRef<AnalyserNode | null>(null);
	const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
	const recorderRef = useRef<MediaRecorder | null>(null);
	const chunksRef = useRef<Blob[]>([]);
	const mutedRef = useRef(false);

	// Timers
	const callTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
	const turnTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
	const vadRef = useRef<ReturnType<typeof setInterval> | null>(null);

	// State tracking
	const silenceStartRef = useRef<number | null>(null);
	const recordStartRef = useRef<number>(0);
	const isCallActiveRef = useRef(false);
	const playbackRef = useRef<HTMLAudioElement | null>(null);
	const abortRef = useRef<AbortController | null>(null);
	const turnStateRef = useRef<TurnState>("listening");
	turnStateRef.current = turnState;

	// ── Cleanup on unmount ────────────────────────────────────────
	useEffect(() => {
		return () => {
			isCallActiveRef.current = false;
			clearAllTimers();
			stopStream();
			stopPlayback();
			if (abortRef.current) abortRef.current.abort();
			if (audioCtxRef.current) audioCtxRef.current.close().catch(() => {});
		};
	}, []);

	// ── Helpers ───────────────────────────────────────────────────

	function clearAllTimers() {
		for (const ref of [callTimerRef, turnTimerRef, vadRef]) {
			if (ref.current) {
				clearInterval(ref.current);
				ref.current = null;
			}
		}
	}

	function stopStream() {
		const s = streamRef.current;
		if (s) {
			for (const t of s.getTracks()) t.stop();
			streamRef.current = null;
		}
	}

	function stopPlayback() {
		const a = playbackRef.current;
		if (a) {
			a.pause();
			a.currentTime = 0;
			playbackRef.current = null;
		}
	}

	function stopRecorder() {
		const r = recorderRef.current;
		if (r && r.state !== "inactive") r.stop();
		recorderRef.current = null;
	}

	// ── Start a recording turn ────────────────────────────────────

	const startTurn = useCallback(() => {
		if (!isCallActiveRef.current) return;
		const stream = streamRef.current;
		if (!stream) return;

		chunksRef.current = [];
		const mimeType = pickAudioType();
		const recorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
		recorderRef.current = recorder;

		recorder.ondataavailable = (e: BlobEvent) => {
			if (e.data.size > 0) chunksRef.current.push(e.data);
		};

		recorder.onstop = () => {
			if (!isCallActiveRef.current) return;
			const elapsed = Date.now() - recordStartRef.current;
			if (elapsed < MIN_RECORDING_MS || mutedRef.current) {
				// Too short or muted - skip and restart listening
				if (isCallActiveRef.current) beginListening();
				return;
			}
			const blob = new Blob(chunksRef.current, { type: recorder.mimeType || "audio/webm" });
			chunksRef.current = [];
			void processTurn(blob);
		};

		recorder.start(250);
		recordStartRef.current = Date.now();
		silenceStartRef.current = null;

		// Turn timer
		if (turnTimerRef.current) clearInterval(turnTimerRef.current);
		const turnStart = Date.now();
		turnTimerRef.current = setInterval(() => {
			setTurnSeconds(Math.floor((Date.now() - turnStart) / 1000));
		}, 500);

		setTurnState("listening");
		startVAD(stream);
	}, []);

	// ── Voice Activity Detection ─────────────────────────────────

	function startVAD(stream: MediaStream) {
		if (vadRef.current) clearInterval(vadRef.current);

		// Reuse existing AudioContext or create new one
		if (!audioCtxRef.current || audioCtxRef.current.state === "closed") {
			audioCtxRef.current = new AudioContext();
		}
		const ctx = audioCtxRef.current;
		if (ctx.state === "suspended") ctx.resume();

		// Only create new source/analyser if needed
		if (!analyserRef.current) {
			const analyser = ctx.createAnalyser();
			analyser.fftSize = 256;
			analyser.smoothingTimeConstant = 0.3;
			analyserRef.current = analyser;

			const source = ctx.createMediaStreamSource(stream);
			source.connect(analyser);
			sourceRef.current = source;
		}

		const analyser = analyserRef.current;
		const buf = new Uint8Array(analyser.frequencyBinCount);

		vadRef.current = setInterval(() => {
			if (!isCallActiveRef.current) return;
			if (mutedRef.current) return;

			analyser.getByteTimeDomainData(buf);
			let sum = 0;
			for (let i = 0; i < buf.length; i++) {
				const v = (buf[i] - 128) / 128;
				sum += v * v;
			}
			const rms = Math.sqrt(sum / buf.length);

			if (rms > SILENCE_THRESHOLD) {
				// Voice detected
				silenceStartRef.current = null;
				if (turnStateRef.current === "listening") {
					setTurnState("speaking");
				}
			} else if (turnStateRef.current === "speaking") {
				// Silence after speaking
				const now = Date.now();
				if (silenceStartRef.current === null) {
					silenceStartRef.current = now;
				} else if (now - silenceStartRef.current >= SILENCE_DURATION * 1000) {
					// Enough silence - auto-send
					stopVAD();
					if (turnTimerRef.current) {
						clearInterval(turnTimerRef.current);
						turnTimerRef.current = null;
					}
					stopRecorder();
				}
			}
		}, VAD_INTERVAL_MS);
	}

	function stopVAD() {
		if (vadRef.current) {
			clearInterval(vadRef.current);
			vadRef.current = null;
		}
	}

	// ── Process a turn: send audio → get reply → play → loop ────

	async function processTurn(audioBlob: Blob) {
		if (!isCallActiveRef.current) return;
		setTurnState("processing");
		setTurnSeconds(0);

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
			if (controller.signal.aborted || !isCallActiveRef.current) return;

			optsRef.current.onTurnResult?.(result);
			playReply(result.audio);
		} catch (err) {
			if (controller.signal.aborted) return;
			console.error("Voice call turn error:", err);
			toast.error(err instanceof Error ? err.message : "Voice agent turn failed.");
			// Stay in call - restart listening
			if (isCallActiveRef.current) beginListening();
		} finally {
			abortRef.current = null;
		}
	}

	// ── Play agent reply then auto-loop ──────────────────────────

	function playReply(blob: Blob) {
		if (!isCallActiveRef.current) return;
		setTurnState("agent_speaking");

		const url = URL.createObjectURL(blob);
		const audio = new Audio(url);
		playbackRef.current = audio;

		audio.onended = () => {
			URL.revokeObjectURL(url);
			playbackRef.current = null;
			if (isCallActiveRef.current && !mutedRef.current) {
				beginListening();
			} else if (isCallActiveRef.current && mutedRef.current) {
				setTurnState("paused");
			}
		};

		audio.onerror = () => {
			URL.revokeObjectURL(url);
			playbackRef.current = null;
			if (isCallActiveRef.current) beginListening();
		};

		audio.play().catch(() => {
			URL.revokeObjectURL(url);
			playbackRef.current = null;
			if (isCallActiveRef.current) beginListening();
		});
	}

	// ── Begin listening (small delay to let mic settle) ──────────

	function beginListening() {
		if (!isCallActiveRef.current) return;
		setTurnState("listening");
		setTurnSeconds(0);
		// Small delay to avoid rapid re-triggering
		setTimeout(() => startTurn(), 200);
	}

	// ── Public API ────────────────────────────────────────────────

	const startCall = useCallback(async () => {
		if (callState !== "idle" && callState !== "ended") return;

		setCallState("connecting");
		setIsMuted(false);
		mutedRef.current = false;

		let stream: MediaStream;
		try {
			stream = await navigator.mediaDevices.getUserMedia({
				audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true },
			});
		} catch (err) {
			setCallState("idle");
			toast.error(
				err instanceof DOMException && err.name === "NotAllowedError"
					? "Microphone access denied."
					: "Could not access microphone."
			);
			return;
		}

		streamRef.current = stream;
		isCallActiveRef.current = true;
		setCallState("active");
		setCallSeconds(0);

		// Call duration timer
		const callStart = Date.now();
		callTimerRef.current = setInterval(() => {
			setCallSeconds(Math.floor((Date.now() - callStart) / 1000));
		}, 1000);

		// First turn
		beginListening();
	}, [callState]);

	const endCall = useCallback(() => {
		isCallActiveRef.current = false;
		clearAllTimers();
		stopRecorder();
		stopPlayback();
		stopStream();

		// Disconnect audio graph
		if (sourceRef.current) {
			try {
				sourceRef.current.disconnect();
			} catch {}
			sourceRef.current = null;
		}
		if (analyserRef.current) {
			try {
				analyserRef.current.disconnect();
			} catch {}
			analyserRef.current = null;
		}
		if (audioCtxRef.current && audioCtxRef.current.state !== "closed") {
			audioCtxRef.current.close().catch(() => {});
			audioCtxRef.current = null;
		}

		if (abortRef.current) {
			abortRef.current.abort();
			abortRef.current = null;
		}

		setCallState("ended");
		setTurnState("listening");
		setCallSeconds(0);
		setTurnSeconds(0);
		setIsMuted(false);

		// Reset to idle after a moment so user can call again
		setTimeout(() => setCallState("idle"), 1000);
	}, []);

	const toggleMute = useCallback(() => {
		const next = !mutedRef.current;
		mutedRef.current = next;
		setIsMuted(next);

		if (next) {
			// Mute: stop current recording, enter paused state
			stopVAD();
			stopRecorder();
			if (turnTimerRef.current) {
				clearInterval(turnTimerRef.current);
				turnTimerRef.current = null;
			}
			stopPlayback();
			setTurnState("paused");
		} else {
			// Unmute: resume listening
			if (isCallActiveRef.current) beginListening();
		}
	}, []);

	const sendNow = useCallback(() => {
		if (turnStateRef.current !== "speaking" && turnStateRef.current !== "listening") return;
		stopVAD();
		if (turnTimerRef.current) {
			clearInterval(turnTimerRef.current);
			turnTimerRef.current = null;
		}
		// Force-stop recorder (onstop handler will process the audio)
		stopRecorder();
	}, []);

	return {
		callState,
		turnState,
		callSeconds,
		turnSeconds,
		isMuted,
		startCall,
		endCall,
		toggleMute,
		sendNow,
	};
}
