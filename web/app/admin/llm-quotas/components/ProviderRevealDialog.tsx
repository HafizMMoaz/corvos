"use client";

import { Check, Copy } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Spinner } from "@/components/ui/spinner";
import type { AdminLlmProviderRead } from "@/contracts/types/admin-llm.types";
import { copyToClipboard } from "@/lib/utils";

interface ProviderRevealDialogProps {
	/** Provider whose key is being revealed, or null when the dialog should be closed. */
	provider: AdminLlmProviderRead | null;
	onOpenChange: (open: boolean) => void;
	onReveal: (id: number) => Promise<string | null>;
}

/**
 * Reveal + copy flow for a provider's plaintext API key -- same UX as
 * `ApiKeyContent`'s "copy your key now" dialog, except the value is fetched
 * on open from `POST /admin/llm-providers/{id}/reveal` rather than being
 * handed a freshly-created value.
 */
export function ProviderRevealDialog({
	provider,
	onOpenChange,
	onReveal,
}: ProviderRevealDialogProps) {
	const [isRevealing, setIsRevealing] = useState(false);
	const [revealedKey, setRevealedKey] = useState<string | null>(null);
	const [copied, setCopied] = useState(false);

	// Only re-run when the target provider's id changes: onOpenChange is a fresh
	// inline closure every render of ProvidersContent, and including it (or the
	// whole provider object) would re-fire this effect, and re-call the reveal
	// endpoint, on unrelated parent re-renders.
	// biome-ignore lint/correctness/useExhaustiveDependencies: see comment above
	useEffect(() => {
		if (!provider) {
			setRevealedKey(null);
			setCopied(false);
			return;
		}
		let cancelled = false;
		setIsRevealing(true);
		onReveal(provider.id)
			.then((key) => {
				if (!cancelled) setRevealedKey(key);
			})
			.catch(() => {
				if (!cancelled) onOpenChange(false);
			})
			.finally(() => {
				if (!cancelled) setIsRevealing(false);
			});
		return () => {
			cancelled = true;
		};
	}, [provider?.id]);

	async function handleCopy() {
		if (!revealedKey) return;
		const success = await copyToClipboard(revealedKey);
		if (success) {
			setCopied(true);
			setTimeout(() => setCopied(false), 2000);
		}
	}

	return (
		<Dialog open={provider !== null} onOpenChange={onOpenChange}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>API key for {provider?.display_name}</DialogTitle>
					<DialogDescription>
						This is the exact value stored for this provider. Keep it somewhere secure.
					</DialogDescription>
				</DialogHeader>

				{isRevealing ? (
					<div className="flex items-center justify-center py-6">
						<Spinner size="sm" />
					</div>
				) : (
					<div className="flex items-center gap-2 rounded-md border border-border/60 bg-muted/30 p-2">
						<code className="min-w-0 flex-1 overflow-x-auto whitespace-nowrap text-xs">
							{revealedKey || "(no value)"}
						</code>
						<Button
							variant="outline"
							size="sm"
							onClick={handleCopy}
							disabled={!revealedKey}
							className="border-0 bg-muted/30 hover:bg-muted/50"
							aria-label="Copy API key"
						>
							{copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
						</Button>
					</div>
				)}

				<DialogFooter>
					<Button onClick={() => onOpenChange(false)}>Done</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
