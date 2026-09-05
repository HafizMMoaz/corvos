import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";

export interface VoiceSettings {
	/** Selected ElevenLabs voice ID (unprefixed native ref), or null for the default. */
	voiceId: string | null;
	/** Selected voice display name (for UI badges). */
	voiceName: string | null;
	/** BCP-47 language code for STT hint + reply language, or null for auto-detect. */
	language: string | null;
}

const DEFAULT_SETTINGS: VoiceSettings = {
	voiceId: null,
	voiceName: null,
	language: null,
};

export const voiceSettingsAtom = atomWithStorage<VoiceSettings>(
	"voice-settings:v1",
	DEFAULT_SETTINGS
);

/** Patch part of the persisted voice settings. */
export const patchVoiceSettingsAtom = atom(null, (_, set, patch: Partial<VoiceSettings>) => {
	set(voiceSettingsAtom, (prev) => ({ ...prev, ...patch }));
});
