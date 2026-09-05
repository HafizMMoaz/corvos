"use client";

import { useQuery } from "@tanstack/react-query";
import { useAtomValue, useSetAtom } from "jotai";
import { AudioLines, Check, Loader2, Play, Square } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "sonner";
import { patchVoiceSettingsAtom, voiceSettingsAtom } from "@/atoms/voice/voice-settings.atom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { type LibraryVoice, voiceApiService } from "@/lib/apis/voice-api.service";
import { cn } from "@/lib/utils";

// ── Voice sample cache (one preview per voice per page lifetime) ───────

const sampleUrls = new Map<string, Promise<Blob>>();
let activePreview: HTMLAudioElement | null = null;
let stopActivePreview: (() => void) | null = null;

function getSampleBlob(voiceId: string): Promise<Blob> {
	let blob = sampleUrls.get(voiceId);
	if (!blob) {
		blob = voiceApiService.previewVoice(voiceId);
		blob.catch(() => sampleUrls.delete(voiceId));
		sampleUrls.set(voiceId, blob);
	}
	return blob;
}

// ── Component ──────────────────────────────────────────────────────────

export function VoiceSettingsPopover() {
	const [open, setOpen] = useState(false);
	const [search, setSearch] = useState("");
	const [librarySearch, setLibrarySearch] = useState("");
	const settings = useAtomValue(voiceSettingsAtom);
	const patchSettings = useSetAtom(patchVoiceSettingsAtom);

	const { data: languages } = useQuery({
		queryKey: ["voice-languages"],
		queryFn: () => voiceApiService.listLanguages(),
		staleTime: Infinity,
		enabled: open,
	});

	const { data: catalogVoices, isLoading: catalogLoading } = useQuery({
		queryKey: ["voice-catalog"],
		queryFn: () => voiceApiService.listVoices(),
		staleTime: 5 * 60 * 1000,
		enabled: open,
	});

	const { data: libraryVoices, isLoading: libraryLoading } = useQuery({
		queryKey: ["voice-library"],
		queryFn: () => voiceApiService.listLibraryVoices(),
		staleTime: 5 * 60 * 1000,
		enabled: open,
		retry: false,
	});

	const filteredCatalog = useMemo(() => {
		if (!catalogVoices) return [];
		const q = search.trim().toLowerCase();
		if (!q) return catalogVoices;
		return catalogVoices.filter(
			(v) =>
				v.display_name.toLowerCase().includes(q) ||
				(v.accent ?? "").toLowerCase().includes(q) ||
				v.language.toLowerCase().includes(q)
		);
	}, [catalogVoices, search]);

	const filteredLibrary = useMemo(() => {
		if (!libraryVoices) return [];
		const q = librarySearch.trim().toLowerCase();
		if (!q) return libraryVoices;
		return libraryVoices.filter(
			(v) =>
				v.name.toLowerCase().includes(q) ||
				(v.accent ?? "").toLowerCase().includes(q) ||
				(v.language ?? "").toLowerCase().includes(q) ||
				(v.description ?? "").toLowerCase().includes(q)
		);
	}, [libraryVoices, librarySearch]);

	// Accent groups for the library (indian, pakistani, chinese, ...)
	const libraryByAccent = useMemo(() => {
		const groups = new Map<string, LibraryVoice[]>();
		for (const v of filteredLibrary) {
			const key = v.accent ?? "other";
			const list = groups.get(key) ?? [];
			list.push(v);
			groups.set(key, list);
		}
		return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b));
	}, [filteredLibrary]);

	return (
		<Popover open={open} onOpenChange={setOpen}>
			<PopoverTrigger asChild>
				<Button
					type="button"
					variant="ghost"
					size="icon"
					className={cn(
						"size-9 shrink-0 rounded-full transition-all",
						settings.voiceId || settings.language
							? "text-primary"
							: "text-muted-foreground hover:text-foreground"
					)}
					aria-label="Voice settings"
					title="Change agent voice and language"
				>
					<AudioLines className="size-5" />
				</Button>
			</PopoverTrigger>
			<PopoverContent align="end" side="top" className="w-96 p-0" sideOffset={8}>
				<div className="flex flex-col gap-3 p-3">
					{/* Language picker */}
					<div className="flex items-center justify-between gap-2">
						<span className="text-xs font-medium text-muted-foreground shrink-0">Language</span>
						<Select
							value={settings.language ?? "auto"}
							onValueChange={(value) =>
								patchSettings({ language: value === "auto" ? null : value })
							}
						>
							<SelectTrigger className="h-8 flex-1 text-xs">
								<SelectValue placeholder="Auto-detect" />
							</SelectTrigger>
							<SelectContent>
								<SelectItem value="auto" className="text-xs">
									Auto-detect
								</SelectItem>
								{(languages ?? []).map((lang) => (
									<SelectItem key={lang.code} value={lang.code} className="text-xs">
										{lang.flag} {lang.name}
										<span className="text-muted-foreground"> · {lang.native_name}</span>
									</SelectItem>
								))}
							</SelectContent>
						</Select>
					</div>

					{/* Voice picker */}
					<Tabs defaultValue="library">
						<TabsList className="grid w-full grid-cols-2">
							<TabsTrigger value="library" className="text-xs">
								Voice Library ({libraryVoices?.length ?? 0})
							</TabsTrigger>
							<TabsTrigger value="default" className="text-xs">
								Default ({catalogVoices?.length ?? 0})
							</TabsTrigger>
						</TabsList>

						{/* Library voices (accent-filtered) */}
						<TabsContent value="library" className="mt-2">
							<Input
								value={librarySearch}
								onChange={(e) => setLibrarySearch(e.target.value)}
								placeholder="Search accents: indian, pakistani, chinese..."
								className="h-8 mb-2 text-xs"
							/>
							<ScrollArea className="h-64 pr-2">
								{libraryLoading ? (
									<div className="flex items-center justify-center py-8 text-muted-foreground text-xs">
										<Loader2 className="size-4 animate-spin mr-2" />
										Loading voice library...
									</div>
								) : libraryByAccent.length === 0 ? (
									<div className="py-6 text-center text-xs text-muted-foreground">
										No voices found. Add voices to your ElevenLabs library to get more accents.
									</div>
								) : (
									<div className="flex flex-col gap-3">
										{libraryByAccent.map(([accent, voices]) => (
											<div key={accent}>
												<div className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
													{accent} accent
												</div>
												{voices.map((voice) => (
													<VoiceRow
														key={voice.voice_id}
														voiceId={voice.voice_id}
														name={voice.name}
														subtitle={[voice.language, voice.gender, voice.description]
															.filter(Boolean)
															.join(" · ")}
														previewUrl={voice.preview_url}
														selected={settings.voiceId === voice.voice_id}
														onSelect={() =>
															patchSettings({
																voiceId: voice.voice_id,
																voiceName: voice.name,
															})
														}
													/>
												))}
											</div>
										))}
									</div>
								)}
							</ScrollArea>
						</TabsContent>

						{/* Default catalog voices */}
						<TabsContent value="default" className="mt-2">
							<Input
								value={search}
								onChange={(e) => setSearch(e.target.value)}
								placeholder="Search voices..."
								className="h-8 mb-2 text-xs"
							/>
							<ScrollArea className="h-64 pr-2">
								{catalogLoading ? (
									<div className="flex items-center justify-center py-8 text-muted-foreground text-xs">
										<Loader2 className="size-4 animate-spin mr-2" />
										Loading voices...
									</div>
								) : filteredCatalog.length === 0 ? (
									<div className="py-6 text-center text-xs text-muted-foreground">
										No voices match your search.
									</div>
								) : (
									filteredCatalog.map((voice) => (
										<VoiceRow
											key={voice.voice_id}
											voiceId={voice.voice_id}
											name={voice.display_name}
											subtitle={[
												voice.accent ? `${voice.accent} accent` : null,
												voice.gender,
												voice.language === "*" ? "multilingual" : voice.language,
											]
												.filter(Boolean)
												.join(" · ")}
											selected={settings.voiceId === voice.voice_id}
											onSelect={() =>
												patchSettings({
													voiceId: voice.voice_id,
													voiceName: voice.display_name,
												})
											}
										/>
									))
								)}
							</ScrollArea>
						</TabsContent>
					</Tabs>

					{/* Reset */}
					{(settings.voiceId || settings.language) && (
						<Button
							type="button"
							variant="ghost"
							size="sm"
							className="h-7 text-xs text-muted-foreground"
							onClick={() => patchSettings({ voiceId: null, voiceName: null, language: null })}
						>
							Reset to defaults
						</Button>
					)}
				</div>
			</PopoverContent>
		</Popover>
	);
}

// ── One voice row: name, tags, preview, select ─────────────────────────

function VoiceRow({
	voiceId,
	name,
	subtitle,
	previewUrl,
	selected,
	onSelect,
}: {
	voiceId: string;
	name: string;
	subtitle?: string;
	/** Direct MP3 preview URL (library voices have one); catalog voices synthesize on demand. */
	previewUrl?: string | null;
	selected: boolean;
	onSelect: () => void;
}) {
	const [previewState, setPreviewState] = useState<"idle" | "loading" | "playing">("idle");
	const mountedRef = useRef(true);

	useEffect(() => {
		mountedRef.current = true;
		return () => {
			mountedRef.current = false;
			if (stopActivePreview && activePreview?.dataset.voiceId === voiceId) {
				stopActivePreview();
			}
		};
	}, [voiceId]);

	const playPreview = async () => {
		if (stopActivePreview) stopActivePreview();
		setPreviewState("loading");
		try {
			let url: string;
			if (previewUrl) {
				// Library voices ship a hosted preview MP3
				url = previewUrl;
			} else {
				const blob = await getSampleBlob(voiceId.replace(/^elevenlabs:/, ""));
				url = URL.createObjectURL(blob);
			}
			if (!mountedRef.current) return;

			const audio = new Audio(url);
			audio.dataset.voiceId = voiceId;
			activePreview = audio;
			stopActivePreview = () => {
				audio.pause();
				if (!previewUrl) URL.revokeObjectURL(url);
				activePreview = null;
				stopActivePreview = null;
				if (mountedRef.current) setPreviewState("idle");
			};
			audio.onended = () => {
				if (activePreview === audio) {
					activePreview = null;
					stopActivePreview = null;
				}
				if (!previewUrl) URL.revokeObjectURL(url);
				if (mountedRef.current) setPreviewState("idle");
			};
			await audio.play();
			if (mountedRef.current) setPreviewState("playing");
		} catch (err) {
			if (mountedRef.current) setPreviewState("idle");
			toast.error(err instanceof Error ? err.message : "Couldn't play the voice sample");
		}
	};

	const stopPreview = () => {
		if (stopActivePreview) stopActivePreview();
	};

	return (
		<div
			role="option"
			aria-selected={selected}
			tabIndex={0}
			className={cn(
				"flex items-center gap-2 rounded-lg px-2 py-1.5 cursor-pointer transition-colors",
				selected ? "bg-primary/10" : "hover:bg-accent"
			)}
			onClick={onSelect}
			onKeyDown={(e) => {
				if (e.key === "Enter" || e.key === " ") {
					e.preventDefault();
					onSelect();
				}
			}}
		>
			<div className="flex-1 min-w-0">
				<div className="flex items-center gap-1.5">
					<span className="text-xs font-medium truncate">{name}</span>
					{selected && <Check className="size-3 text-primary shrink-0" />}
				</div>
				{subtitle && <div className="text-[10px] text-muted-foreground truncate">{subtitle}</div>}
			</div>
			<Button
				type="button"
				variant="ghost"
				size="icon"
				className="size-6 shrink-0 rounded-full"
				aria-label={previewState === "playing" ? "Stop preview" : "Play preview"}
				disabled={previewState === "loading"}
				onClick={(e) => {
					e.stopPropagation();
					if (previewState === "playing") stopPreview();
					else void playPreview();
				}}
			>
				{previewState === "loading" ? (
					<Loader2 className="size-3 animate-spin" />
				) : previewState === "playing" ? (
					<Square className="size-3" />
				) : (
					<Play className="size-3" />
				)}
			</Button>
		</div>
	);
}
