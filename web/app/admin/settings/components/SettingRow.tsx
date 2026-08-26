"use client";

import { Check, Copy, Eye, EyeOff, Pencil, RotateCcw, ShieldAlert } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import type { AdminSettingRead, AdminSettingValue } from "@/contracts/types/admin-settings.types";
import { formatSettingValue } from "@/lib/admin-setting-value";
import { copyToClipboard } from "@/lib/utils";
import { useAdminPermissions } from "../../admin-shell";
import { SettingConfirmDialog } from "./SettingConfirmDialog";
import { SettingEditDialog } from "./SettingEditDialog";

// PlatformPermission values, from backend/app/db.py. settings:read (which
// every viewer of this page necessarily holds) covers the masked list only.
const SETTINGS_WRITE = "settings:write";
const SETTINGS_REVEAL = "settings:reveal";

const NO_WRITE_HINT = "Requires the settings:write permission";
const NO_REVEAL_HINT = "Requires the settings:reveal permission";

interface SettingRowProps {
	setting: AdminSettingRead;
	isMutating: boolean;
	onUpdate: (key: string, value: AdminSettingValue) => Promise<void>;
	onRevert: (key: string) => Promise<void>;
	onReveal: (key: string) => Promise<AdminSettingValue>;
}

const DISRUPTIVE_WARNING =
	"This is a disruptive change - it may invalidate sessions, restart services, or otherwise affect the running platform.";

/**
 * Values arrive as real JSON types, so they have to be stringified explicitly
 * before they reach JSX: React renders nothing at all for a bare `false`,
 * which would show an empty value box for every disabled boolean setting.
 * `fallback` covers null and empty-string values, which mean different things
 * depending on where they show up.
 */
function displayText(value: AdminSettingValue, fallback: string): string {
	return formatSettingValue(value) || fallback;
}

export function SettingRow({ setting, isMutating, onUpdate, onRevert, onReveal }: SettingRowProps) {
	// A settings:read-only admin can see this page but can't change or reveal
	// anything, so don't offer controls that would only ever come back 403.
	const { has } = useAdminPermissions();
	const canWrite = has(SETTINGS_WRITE);
	const canReveal = has(SETTINGS_REVEAL);

	const [editOpen, setEditOpen] = useState(false);

	const [confirmUpdateOpen, setConfirmUpdateOpen] = useState(false);
	// Boxed rather than held bare, so a pending `false`/`null`/`0` (all
	// legitimate setting values) isn't mistaken for "nothing pending".
	const [pendingValue, setPendingValue] = useState<{ value: AdminSettingValue } | null>(null);

	const [revertOpen, setRevertOpen] = useState(false);

	// isRevealed is tracked separately from revealedValue so a legitimately
	// null/empty revealed value doesn't get mistaken for "not yet revealed".
	const [isRevealed, setIsRevealed] = useState(false);
	const [revealedValue, setRevealedValue] = useState<AdminSettingValue>(null);
	const [isRevealing, setIsRevealing] = useState(false);
	const [copied, setCopied] = useState(false);

	const displayValue = setting.is_secret
		? isRevealed
			? displayText(revealedValue, "(no value)")
			: displayText(setting.value, "***")
		: displayText(setting.value, "(not set)");

	async function submitUpdate(value: AdminSettingValue): Promise<boolean> {
		try {
			await onUpdate(setting.key, value);
			return true;
		} catch {
			// hook already surfaced a toast with the server's validation message
			return false;
		}
	}

	async function handleEditSubmit(value: AdminSettingValue) {
		if (setting.is_disruptive) {
			setEditOpen(false);
			setPendingValue({ value });
			setConfirmUpdateOpen(true);
			return;
		}

		if (await submitUpdate(value)) {
			setEditOpen(false);
		}
	}

	async function handleConfirmDisruptiveUpdate() {
		if (pendingValue === null) return;
		if (await submitUpdate(pendingValue.value)) {
			setConfirmUpdateOpen(false);
			setPendingValue(null);
		}
	}

	async function handleConfirmRevert() {
		try {
			await onRevert(setting.key);
			setRevertOpen(false);
		} catch {
			// hook already surfaced a toast; keep the dialog open to retry
		}
	}

	async function revealValue(): Promise<AdminSettingValue> {
		setIsRevealing(true);
		try {
			const value = await onReveal(setting.key);
			setRevealedValue(value);
			setIsRevealed(true);
			return value;
		} catch {
			return null;
		} finally {
			setIsRevealing(false);
		}
	}

	async function handleToggleReveal() {
		if (isRevealed) {
			setIsRevealed(false);
			return;
		}
		await revealValue();
	}

	async function handleCopy() {
		const valueToCopy = isRevealed ? revealedValue : await revealValue();
		const text = formatSettingValue(valueToCopy);
		if (!text) return;

		const success = await copyToClipboard(text);
		if (success) {
			setCopied(true);
			setTimeout(() => setCopied(false), 2000);
		}
	}

	return (
		<Card className="border-accent bg-accent/20 transition-all duration-200 hover:shadow-md">
			<CardContent className="flex items-start gap-3 p-4">
				<div className="min-w-0 flex-1 space-y-1.5">
					<div className="flex flex-wrap items-center gap-2">
						<h4 className="truncate font-mono text-sm font-semibold tracking-tight">
							{setting.key}
						</h4>
						<Badge variant="outline" className="text-[10px]">
							{setting.value_type}
						</Badge>
						{setting.is_disruptive && (
							<Badge variant="destructive" className="gap-1 text-[10px]">
								<ShieldAlert className="h-3 w-3" />
								Disruptive
							</Badge>
						)}
					</div>

					{setting.description && (
						<p className="text-xs text-muted-foreground">{setting.description}</p>
					)}

					<div className="flex items-center gap-1 pt-0.5">
						<code className="min-w-0 flex-1 truncate rounded bg-muted/50 px-2 py-1 text-xs">
							{displayValue}
						</code>
						{setting.is_secret && (
							<>
								<Button
									type="button"
									variant="ghost"
									size="icon"
									className="h-7 w-7 shrink-0 text-muted-foreground"
									onClick={handleToggleReveal}
									disabled={isRevealing || !canReveal}
									title={canReveal ? undefined : NO_REVEAL_HINT}
									aria-label={isRevealed ? "Hide value" : "Reveal value"}
								>
									{isRevealing ? (
										<Spinner size="xs" />
									) : isRevealed ? (
										<EyeOff className="h-4 w-4" />
									) : (
										<Eye className="h-4 w-4" />
									)}
								</Button>
								<Button
									type="button"
									variant="ghost"
									size="icon"
									className="h-7 w-7 shrink-0 text-muted-foreground"
									onClick={handleCopy}
									disabled={!canReveal}
									title={canReveal ? undefined : NO_REVEAL_HINT}
									aria-label="Copy value"
								>
									{copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
								</Button>
							</>
						)}
					</div>

					<p className="text-[11px] text-muted-foreground">
						{setting.has_override
							? `Updated ${setting.updated_at ? new Date(setting.updated_at).toLocaleString() : "recently"}${setting.updated_by_id ? ` by ${setting.updated_by_id}` : ""}`
							: "Using default value"}
					</p>
				</div>

				<div className="flex shrink-0 gap-1">
					<Button
						variant="ghost"
						size="icon"
						className="h-8 w-8"
						onClick={() => setEditOpen(true)}
						disabled={isMutating || !canWrite}
						title={canWrite ? undefined : NO_WRITE_HINT}
						aria-label={`Edit ${setting.key}`}
					>
						<Pencil className="h-4 w-4" />
					</Button>
					<Button
						variant="ghost"
						size="icon"
						className="h-8 w-8 text-muted-foreground hover:text-destructive"
						onClick={() => setRevertOpen(true)}
						disabled={isMutating || !canWrite}
						title={canWrite ? undefined : NO_WRITE_HINT}
						aria-label={`Revert ${setting.key} to default`}
					>
						<RotateCcw className="h-4 w-4" />
					</Button>
				</div>
			</CardContent>

			<SettingEditDialog
				setting={setting}
				open={editOpen}
				onOpenChange={setEditOpen}
				isMutating={isMutating}
				onSubmit={handleEditSubmit}
			/>

			{/* Disruptive-change confirm, shown before the update actually submits */}
			<SettingConfirmDialog
				open={confirmUpdateOpen}
				onOpenChange={(open) => {
					setConfirmUpdateOpen(open);
					if (!open) setPendingValue(null);
				}}
				isMutating={isMutating}
				title="Confirm disruptive change?"
				description={
					<>
						{setting.description ? `${setting.description} ` : ""}
						{DISRUPTIVE_WARNING}
					</>
				}
				confirmLabel="Confirm change"
				pendingLabel="Saving..."
				showShieldIcon
				onConfirm={handleConfirmDisruptiveUpdate}
			/>

			{/* Revert-to-default confirm */}
			<SettingConfirmDialog
				open={revertOpen}
				onOpenChange={setRevertOpen}
				isMutating={isMutating}
				title="Revert to default?"
				description={
					<>
						<span className="font-mono font-medium text-foreground">{setting.key}</span> will revert
						to its default value. This cannot be undone.
						{setting.is_disruptive && <span className="mt-2 block">{DISRUPTIVE_WARNING}</span>}
					</>
				}
				confirmLabel="Revert"
				pendingLabel="Reverting..."
				showShieldIcon={setting.is_disruptive}
				onConfirm={handleConfirmRevert}
			/>
		</Card>
	);
}
