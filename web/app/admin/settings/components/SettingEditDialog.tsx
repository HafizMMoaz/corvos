"use client";

import { Eye, EyeOff } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
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
import { Switch } from "@/components/ui/switch";
import type { AdminSettingRead, AdminSettingValue } from "@/contracts/types/admin-settings.types";
import { formatSettingValue, parseSettingDraft } from "@/lib/admin-setting-value";

interface SettingEditDialogProps {
	setting: AdminSettingRead;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	isMutating: boolean;
	/**
	 * Called on Save with the draft already converted to the JSON type the
	 * setting's `value_type` declares. The caller owns closing the dialog.
	 */
	onSubmit: (value: AdminSettingValue) => void;
}

/**
 * Edit dialog for a single setting's value - type-aware input (a `Switch` for
 * bools, a masked input with its own show/hide toggle for secrets, a numeric
 * or text input otherwise). Rendered once per row by SettingRow.
 */
export function SettingEditDialog({
	setting,
	open,
	onOpenChange,
	isMutating,
	onSubmit,
}: SettingEditDialogProps) {
	const isBoolean = setting.value_type === "bool";
	const isNumeric = setting.value_type === "int" || setting.value_type === "float";
	const editId = `setting-value-${setting.key}`;

	const [draftValue, setDraftValue] = useState("");
	const [draftBoolean, setDraftBoolean] = useState(false);
	const [showDraftValue, setShowDraftValue] = useState(false);

	// Reset the draft to the setting's current value every time the dialog
	// opens. `setting.value` is whatever JSON type the setting declares (bool,
	// number, string, ...), so it has to be rendered to text for the input.
	useEffect(() => {
		if (!open) return;
		setDraftValue(setting.is_secret ? "" : formatSettingValue(setting.value));
		setDraftBoolean(setting.value === true);
		setShowDraftValue(false);
	}, [open, setting.is_secret, setting.value]);

	// The server validates values strictly by type (a "bool" setting rejects
	// "true", an "int" setting rejects "5"), so convert here and block Save on
	// anything that wouldn't survive the round trip.
	const parsedDraft = useMemo(
		() =>
			isBoolean
				? ({ ok: true, value: draftBoolean } as const)
				: parseSettingDraft(setting.value_type, draftValue),
		[isBoolean, draftBoolean, setting.value_type, draftValue]
	);

	const draftError = !parsedDraft.ok && draftValue.trim() !== "" ? parsedDraft.error : null;

	function handleSubmit() {
		if (!parsedDraft.ok) return;
		onSubmit(parsedDraft.value);
	}

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle className="font-mono">{setting.key}</DialogTitle>
					<DialogDescription>
						{setting.description || "Update this setting's value."}
					</DialogDescription>
				</DialogHeader>

				<div className="space-y-2">
					<Label htmlFor={editId}>Value</Label>
					{isBoolean ? (
						<div className="flex items-center gap-2">
							<Switch
								id={editId}
								checked={draftBoolean}
								onCheckedChange={setDraftBoolean}
								disabled={isMutating}
							/>
							<span className="text-sm text-muted-foreground">
								{draftBoolean ? "Enabled" : "Disabled"}
							</span>
						</div>
					) : setting.is_secret ? (
						<div className="relative">
							<Input
								id={editId}
								value={draftValue}
								onChange={(event) => setDraftValue(event.target.value)}
								placeholder="Enter a new value"
								type={showDraftValue ? "text" : "password"}
								className="pr-11"
								disabled={isMutating}
							/>
							<Button
								type="button"
								variant="ghost"
								size="icon"
								className="absolute top-1/2 right-1 size-8 -translate-y-1/2 text-muted-foreground"
								onClick={() => setShowDraftValue((current) => !current)}
								disabled={!draftValue}
								aria-label={showDraftValue ? "Hide value" : "Show value"}
							>
								{showDraftValue ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
							</Button>
						</div>
					) : (
						<Input
							id={editId}
							value={draftValue}
							onChange={(event) => setDraftValue(event.target.value)}
							type={isNumeric ? "number" : "text"}
							disabled={isMutating}
							aria-invalid={draftError !== null}
						/>
					)}
					{draftError && <p className="text-xs text-destructive">{draftError}</p>}
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
						size="sm"
						disabled={isMutating || !parsedDraft.ok}
						onClick={handleSubmit}
						className="relative min-w-[100px]"
					>
						<span className={isMutating ? "opacity-0" : ""}>Save changes</span>
						{isMutating && <Spinner size="sm" className="absolute" />}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
