"use client";

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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Textarea } from "@/components/ui/textarea";
import type {
	FeatureFlagCreateRequest,
	FeatureFlagRead,
	FeatureFlagUpdateRequest,
} from "@/contracts/types/admin-billing.types";

interface FeatureFlagFormDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	/** Flag being edited, or null when the dialog is in create mode. */
	flag: FeatureFlagRead | null;
	isMutating: boolean;
	onCreate: (body: FeatureFlagCreateRequest) => Promise<void>;
	onUpdate: (id: number, body: FeatureFlagUpdateRequest) => Promise<void>;
}

interface FlagDraft {
	flagKey: string;
	name: string;
	description: string;
}

const EMPTY_DRAFT: FlagDraft = { flagKey: "", name: "", description: "" };

/** Create/edit dialog for a feature flag definition (three fields, no more). */
export function FeatureFlagFormDialog({
	open,
	onOpenChange,
	flag,
	isMutating,
	onCreate,
	onUpdate,
}: FeatureFlagFormDialogProps) {
	const isEditing = flag !== null;
	const [draft, setDraft] = useState<FlagDraft>(EMPTY_DRAFT);

	useEffect(() => {
		if (!open) return;
		setDraft(
			flag
				? {
						flagKey: flag.flag_key,
						name: flag.name,
						description: flag.description ?? "",
					}
				: EMPTY_DRAFT
		);
	}, [open, flag]);

	const valid = draft.flagKey.trim() !== "" && draft.name.trim() !== "";

	async function handleSubmit() {
		if (!valid) return;
		try {
			if (isEditing && flag) {
				await onUpdate(flag.id, {
					flag_key: draft.flagKey.trim(),
					name: draft.name.trim(),
					description: draft.description.trim() === "" ? null : draft.description.trim(),
				});
			} else {
				await onCreate({
					flag_key: draft.flagKey.trim(),
					name: draft.name.trim(),
					description: draft.description.trim() === "" ? null : draft.description.trim(),
				});
			}
			onOpenChange(false);
		} catch {
			// hook already surfaced a toast; keep the dialog open to retry
		}
	}

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-w-lg">
				<DialogHeader>
					<DialogTitle>{isEditing ? "Edit feature flag" : "Add feature flag"}</DialogTitle>
					<DialogDescription>
						{isEditing
							? "Update this feature flag definition."
							: "Define a feature that plans can enable."}
					</DialogDescription>
				</DialogHeader>

				<div className="space-y-4">
					<div className="space-y-2">
						<Label htmlFor="flag-key">Flag key</Label>
						<Input
							id="flag-key"
							value={draft.flagKey}
							onChange={(event) => setDraft({ ...draft, flagKey: event.target.value })}
							placeholder="advanced_rag"
							className="font-mono"
							disabled={isMutating}
						/>
						<p className="text-xs text-muted-foreground">
							Stable machine identifier (unique across flags).
						</p>
					</div>

					<div className="space-y-2">
						<Label htmlFor="flag-name">Name</Label>
						<Input
							id="flag-name"
							value={draft.name}
							onChange={(event) => setDraft({ ...draft, name: event.target.value })}
							placeholder="Advanced RAG"
							disabled={isMutating}
						/>
					</div>

					<div className="space-y-2">
						<Label htmlFor="flag-description">Description</Label>
						<Textarea
							id="flag-description"
							value={draft.description}
							onChange={(event) => setDraft({ ...draft, description: event.target.value })}
							placeholder="What this feature controls"
							rows={2}
							disabled={isMutating}
						/>
					</div>
				</div>

				<DialogFooter>
					<Button
						type="button"
						variant="secondary"
						size="sm"
						onClick={() => onOpenChange(false)}
						disabled={isMutating}
					>
						Cancel
					</Button>
					<Button
						type="button"
						size="sm"
						disabled={isMutating || !valid}
						onClick={() => void handleSubmit()}
						className="relative min-w-[100px]"
					>
						<span className={isMutating ? "opacity-0" : ""}>
							{isEditing ? "Save changes" : "Add flag"}
						</span>
						{isMutating && <Spinner size="sm" className="absolute" />}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
