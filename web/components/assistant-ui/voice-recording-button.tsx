"use client";

import { useAtomValue } from "jotai";
import { Loader2, Mic, MicOff, Square, Volume2 } from "lucide-react";
import { useCallback } from "react";
import { toast } from "sonner";
import { voiceSettingsAtom } from "@/atoms/voice/voice-settings.atom";
import { Button } from "@/components/ui/button";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
	type UseVoiceRecordingOptions,
	useVoiceRecording,
	type VoiceAgentResult,
	type VoiceState,
} from "@/hooks/use-voice-recording";
import { cn } from "@/lib/utils";

interface VoiceRecordingButtonProps {
	workspaceId: number;
	threadId?: number | null;
	voiceId?: string;
	onResult?: (result: VoiceAgentResult) => void;
	disabled?: boolean;
}

export function VoiceRecordingButton({
	workspaceId,
	threadId,
	voiceId,
	onResult,
	disabled = false,
}: VoiceRecordingButtonProps) {
	// User-selected voice/language overrides the prop-based default.
	const settings = useAtomValue(voiceSettingsAtom);
	const opts: UseVoiceRecordingOptions = {
		workspaceId,
		threadId,
		voiceId: settings.voiceId ?? voiceId,
		language: settings.language,
		onResult,
	};
	const {
		voiceState,
		recordingSeconds,
		startRecording,
		stopRecording,
		cancelRecording,
		stopPlayback,
	} = useVoiceRecording(opts);

	const handleClick = useCallback(() => {
		switch (voiceState) {
			case "idle":
				void startRecording();
				break;
			case "recording":
				stopRecording();
				break;
			case "playing":
				stopPlayback();
				break;
			default:
				break;
		}
	}, [voiceState, startRecording, stopRecording, stopPlayback]);

	const handleContextMenu = useCallback(
		(e: React.MouseEvent) => {
			if (voiceState === "recording") {
				e.preventDefault();
				cancelRecording();
				toast.info("Recording cancelled");
			}
		},
		[voiceState, cancelRecording]
	);

	const { icon, tooltip, pulseClass, buttonVariant, extraClass } = getVisualState(
		voiceState,
		recordingSeconds,
		disabled
	);

	return (
		<Tooltip>
			<TooltipTrigger asChild>
				<Button
					type="button"
					variant={buttonVariant}
					size="icon"
					className={cn(
						"size-9 shrink-0 rounded-full transition-all",
						extraClass,
						pulseClass,
						disabled && voiceState === "idle" && "cursor-not-allowed opacity-50"
					)}
					aria-label={tooltip}
					disabled={disabled && voiceState === "idle"}
					onClick={handleClick}
					onContextMenu={handleContextMenu}
				>
					{icon}
				</Button>
			</TooltipTrigger>
			<TooltipContent side="bottom">
				{voiceState === "recording"
					? `Recording... ${recordingSeconds}s (click to send, right-click to cancel)`
					: tooltip}
			</TooltipContent>
		</Tooltip>
	);
}

function getVisualState(state: VoiceState, seconds: number, disabled: boolean) {
	switch (state) {
		case "requesting_mic":
			return {
				icon: <Loader2 className="size-5 animate-spin" />,
				tooltip: "Requesting microphone...",
				pulseClass: "",
				buttonVariant: "ghost" as const,
				extraClass: "text-muted-foreground",
			};
		case "recording":
			return {
				icon: <Square className="size-3.5 fill-current" />,
				tooltip: "Stop recording",
				pulseClass: seconds > 0 ? "animate-pulse" : "",
				buttonVariant: "destructive" as const,
				extraClass: "text-destructive-foreground",
			};
		case "processing":
			return {
				icon: <Loader2 className="size-5 animate-spin" />,
				tooltip: "Processing voice...",
				pulseClass: "",
				buttonVariant: "ghost" as const,
				extraClass: "text-primary",
			};
		case "playing":
			return {
				icon: <Volume2 className="size-5" />,
				tooltip: "Stop playback",
				pulseClass: "animate-pulse",
				buttonVariant: "default" as const,
				extraClass: "",
			};
		case "error":
			return {
				icon: <MicOff className="size-5" />,
				tooltip: "Voice unavailable",
				pulseClass: "",
				buttonVariant: "ghost" as const,
				extraClass: "text-destructive",
			};
		default:
			return {
				icon: <Mic className="size-5" />,
				tooltip: disabled ? "Voice chat unavailable" : "Talk to Corvos",
				pulseClass: "",
				buttonVariant: "ghost" as const,
				extraClass: "text-muted-foreground hover:text-foreground",
			};
	}
}
