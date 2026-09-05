"use client";

import { useAtomValue } from "jotai";
import { Loader2, Mic, MicOff, Phone, PhoneOff, Send, Volume2 } from "lucide-react";
import { useCallback } from "react";
import { voiceSettingsAtom } from "@/atoms/voice/voice-settings.atom";
import { Button } from "@/components/ui/button";
import { type TurnState, useVoiceCall, type VoiceAgentResult } from "@/hooks/use-voice-call";

interface VoiceCallPanelProps {
	workspaceId: number;
	threadId?: number | null;
	voiceId?: string;
	onTurnResult?: (result: VoiceAgentResult) => void;
}

export function VoiceCallPanel({
	workspaceId,
	threadId,
	voiceId,
	onTurnResult,
}: VoiceCallPanelProps) {
	// User-selected voice/language overrides the prop-based default.
	const settings = useAtomValue(voiceSettingsAtom);
	const {
		callState,
		turnState,
		callSeconds,
		turnSeconds,
		isMuted,
		startCall,
		endCall,
		toggleMute,
		sendNow,
	} = useVoiceCall({
		workspaceId,
		threadId,
		voiceId: settings.voiceId ?? voiceId,
		language: settings.language,
		onTurnResult,
	});

	const handleStart = useCallback(() => void startCall(), [startCall]);

	if (callState !== "active" && callState !== "connecting") {
		return (
			<Button
				type="button"
				variant="ghost"
				size="icon"
				className="size-9 shrink-0 rounded-full text-muted-foreground hover:text-foreground transition-all"
				aria-label="Start voice call"
				onClick={handleStart}
				title="Start a voice call"
			>
				<Phone className="size-5" />
			</Button>
		);
	}

	if (callState === "connecting") {
		return (
			<div className="flex items-center gap-3 rounded-full bg-primary/10 px-4 py-2 text-sm">
				<Loader2 className="size-4 animate-spin text-primary" />
				<span className="text-primary font-medium">Connecting...</span>
			</div>
		);
	}

	return (
		<div className="flex items-center gap-2 rounded-full bg-primary/5 border border-primary/20 px-3 py-1.5 min-w-0">
			<div className="flex items-center gap-1.5 text-xs tabular-nums text-muted-foreground shrink-0">
				<span className="relative flex size-2">
					<span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-green-500 opacity-75" />
					<span className="relative inline-flex size-2 rounded-full bg-green-500" />
				</span>
				{fmtDur(callSeconds)}
			</div>
			<div className="flex-1 min-w-0">
				<TurnIndicator state={turnState} turnSeconds={turnSeconds} />
			</div>
			<div className="flex items-center gap-1 shrink-0">
				{(turnState === "speaking" || turnState === "listening") && (
					<Button
						type="button"
						variant="ghost"
						size="icon"
						className="size-7 rounded-full"
						aria-label="Send now"
						onClick={sendNow}
						title="Send recording now"
					>
						<Send className="size-3.5" />
					</Button>
				)}
				<Button
					type="button"
					variant={isMuted ? "destructive" : "ghost"}
					size="icon"
					className="size-7 rounded-full"
					aria-label={isMuted ? "Unmute" : "Mute"}
					onClick={toggleMute}
				>
					{isMuted ? <MicOff className="size-3.5" /> : <Mic className="size-3.5" />}
				</Button>
				<Button
					type="button"
					variant="destructive"
					size="icon"
					className="size-7 rounded-full"
					aria-label="End call"
					onClick={endCall}
				>
					<PhoneOff className="size-3.5" />
				</Button>
			</div>
		</div>
	);
}

function TurnIndicator({ state, turnSeconds }: { state: TurnState; turnSeconds: number }) {
	switch (state) {
		case "listening":
			return (
				<span className="flex items-center gap-1.5 text-xs text-muted-foreground">
					<Mic className="size-3" /> Listening...
				</span>
			);
		case "speaking":
			return (
				<span className="flex items-center gap-1.5 text-xs text-primary font-medium">
					<Mic className="size-3 text-primary animate-pulse" />
					You&apos;re speaking
					{turnSeconds > 0 && (
						<span className="text-muted-foreground font-normal tabular-nums">{turnSeconds}s</span>
					)}
				</span>
			);
		case "processing":
			return (
				<span className="flex items-center gap-1.5 text-xs text-primary">
					<Loader2 className="size-3 animate-spin" /> Thinking...
				</span>
			);
		case "agent_speaking":
			return (
				<span className="flex items-center gap-1.5 text-xs text-accent-foreground font-medium">
					<Volume2 className="size-3 animate-pulse" /> Agent speaking
				</span>
			);
		case "paused":
			return (
				<span className="flex items-center gap-1.5 text-xs text-muted-foreground">
					<MicOff className="size-3" /> Muted
				</span>
			);
		default:
			return null;
	}
}

function fmtDur(totalSeconds: number): string {
	const m = Math.floor(totalSeconds / 60);
	const s = totalSeconds % 60;
	return `${m}:${s.toString().padStart(2, "0")}`;
}
