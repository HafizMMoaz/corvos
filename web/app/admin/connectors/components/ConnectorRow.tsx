"use client";

import { Check, Copy, Eye, EyeOff, Pencil, RotateCcw } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import type {
	AdminConnectorCredentialRead,
	RevealConnectorCredentialResponse,
	UpdateConnectorCredentialRequest,
} from "@/contracts/types/admin-connectors.types";
import { copyToClipboard } from "@/lib/utils";
import { useAdminPermissions } from "../../admin-shell";
import { ConnectorEditDialog } from "./ConnectorEditDialog";
import { ConnectorRevertDialog } from "./ConnectorRevertDialog";

// PlatformPermission values, from backend/app/db.py. connectors:read (which
// every viewer of this page necessarily holds) covers the masked list only.
// There is no connectors:reveal permission -- reveal reuses connectors:write,
// same as the LLM provider catalog's key reveal.
const CONNECTORS_WRITE = "connectors:write";

const NO_WRITE_HINT = "Requires the connectors:write permission";

type CredentialField = "client_id" | "client_secret";

interface ConnectorRowProps {
	connector: AdminConnectorCredentialRead;
	isMutating: boolean;
	onUpdate: (connectorKey: string, updates: UpdateConnectorCredentialRequest) => Promise<void>;
	onRevert: (connectorKey: string) => Promise<void>;
	onReveal: (connectorKey: string) => Promise<RevealConnectorCredentialResponse>;
}

/**
 * Renders one credential field's value box across its three distinct states:
 *
 * - stored admin override (`hasValue`): masked `***`, or the plaintext once
 *   revealed. There is no last-4-chars masked variant here, the list endpoint
 *   never sends any part of the value.
 * - no override but a non-empty env-derived `Config` default (`hasDefault`):
 *   the connector is fully functional, it just isn't managed from this page.
 * - neither: genuinely unconfigured.
 *
 * Collapsing the last two into one "(not set)" is what made every
 * `.env`-configured connector look broken here, and made an explicitly
 * cleared secret indistinguishable from one that never existed.
 */
function CredentialValue({
	isRevealed,
	revealedValue,
	hasValue,
	hasDefault,
}: {
	isRevealed: boolean;
	revealedValue: string | null | undefined;
	hasValue: boolean;
	hasDefault: boolean;
}) {
	if (hasValue) {
		return (
			<code
				className="min-w-0 flex-1 truncate rounded bg-muted/50 px-2 py-1 text-xs"
				title="Set via admin override"
			>
				{isRevealed ? revealedValue || "***" : "***"}
			</code>
		);
	}

	return (
		<span
			className="min-w-0 flex-1 truncate px-2 py-1 text-xs italic text-muted-foreground"
			title={
				hasDefault
					? "No admin override - the value from the server environment is in effect"
					: "No admin override and no value in the server environment"
			}
		>
			{hasDefault ? "Using environment default" : "Not configured"}
		</span>
	);
}

export function ConnectorRow({
	connector,
	isMutating,
	onUpdate,
	onRevert,
	onReveal,
}: ConnectorRowProps) {
	// A connectors:read-only admin can see this page but can't change or
	// reveal anything, so don't offer controls that would only ever come back
	// 403.
	const { has } = useAdminPermissions();
	const canWrite = has(CONNECTORS_WRITE);

	const isComposio = connector.connector_key === "composio";

	const [editOpen, setEditOpen] = useState(false);
	const [revertOpen, setRevertOpen] = useState(false);

	// isRevealed is tracked separately from revealedPair so a legitimately
	// null field in the revealed pair isn't mistaken for "not yet revealed".
	// A single reveal covers both fields -- toggling again just re-masks
	// without a second network call.
	const [isRevealed, setIsRevealed] = useState(false);
	const [revealedPair, setRevealedPair] = useState<RevealConnectorCredentialResponse | null>(null);
	const [isRevealing, setIsRevealing] = useState(false);
	const [copiedField, setCopiedField] = useState<CredentialField | null>(null);

	async function revealValues(): Promise<RevealConnectorCredentialResponse | null> {
		setIsRevealing(true);
		try {
			const result = await onReveal(connector.connector_key);
			setRevealedPair(result);
			setIsRevealed(true);
			return result;
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
		await revealValues();
	}

	async function handleCopy(field: CredentialField) {
		const pair = isRevealed ? revealedPair : await revealValues();
		const text = pair?.[field];
		if (!text) return;

		const success = await copyToClipboard(text);
		if (success) {
			setCopiedField(field);
			setTimeout(() => setCopiedField(null), 2000);
		}
	}

	async function handleEditSubmit(payload: UpdateConnectorCredentialRequest) {
		try {
			await onUpdate(connector.connector_key, payload);
			setEditOpen(false);
		} catch {
			// hook already surfaced a toast with the server's validation message
		}
	}

	async function handleConfirmRevert() {
		try {
			await onRevert(connector.connector_key);
			setRevertOpen(false);
		} catch {
			// hook already surfaced a toast; keep the dialog open to retry
		}
	}

	const revertDisabled = isMutating || !canWrite || !connector.has_override;
	const revertTitle = !canWrite
		? NO_WRITE_HINT
		: !connector.has_override
			? "No override to revert"
			: undefined;

	return (
		<Card className="border-accent bg-accent/20 transition-all duration-200 hover:shadow-md">
			<CardContent className="flex items-start gap-3 p-4">
				<div className="min-w-0 flex-1 space-y-1.5">
					<div className="flex flex-wrap items-center gap-2">
						<h4 className="truncate text-sm font-semibold tracking-tight">
							{connector.display_name}
						</h4>
						{connector.is_enabled ? (
							<Badge variant="secondary" className="text-[10px]">
								Enabled
							</Badge>
						) : (
							<Badge variant="outline" className="text-[10px]">
								Disabled
							</Badge>
						)}
					</div>

					{connector.description && (
						<p className="text-xs text-muted-foreground">{connector.description}</p>
					)}

					<div className="space-y-1 pt-0.5">
						{!isComposio && (
							<div className="flex items-center gap-1">
								<span className="w-24 shrink-0 text-[11px] text-muted-foreground">Client ID</span>
								<CredentialValue
									isRevealed={isRevealed}
									revealedValue={revealedPair?.client_id}
									hasValue={connector.has_client_id}
									hasDefault={connector.has_default_client_id}
								/>
								<Button
									type="button"
									variant="ghost"
									size="icon"
									className="h-7 w-7 shrink-0 text-muted-foreground"
									onClick={() => handleCopy("client_id")}
									disabled={!canWrite}
									title={canWrite ? undefined : NO_WRITE_HINT}
									aria-label="Copy client ID"
								>
									{copiedField === "client_id" ? (
										<Check className="h-4 w-4" />
									) : (
										<Copy className="h-4 w-4" />
									)}
								</Button>
							</div>
						)}
						<div className="flex items-center gap-1">
							<span className="w-24 shrink-0 text-[11px] text-muted-foreground">Client Secret</span>
							<CredentialValue
								isRevealed={isRevealed}
								revealedValue={revealedPair?.client_secret}
								hasValue={connector.has_client_secret}
								hasDefault={connector.has_default_client_secret}
							/>
							<Button
								type="button"
								variant="ghost"
								size="icon"
								className="h-7 w-7 shrink-0 text-muted-foreground"
								onClick={() => handleCopy("client_secret")}
								disabled={!canWrite}
								title={canWrite ? undefined : NO_WRITE_HINT}
								aria-label="Copy client secret"
							>
								{copiedField === "client_secret" ? (
									<Check className="h-4 w-4" />
								) : (
									<Copy className="h-4 w-4" />
								)}
							</Button>
						</div>
					</div>

					<p className="text-[11px] text-muted-foreground">
						{connector.has_override
							? `Updated ${connector.updated_at ? new Date(connector.updated_at).toLocaleString() : "recently"}${connector.updated_by_id ? ` by ${connector.updated_by_id}` : ""}`
							: "No override - using environment default"}
					</p>
				</div>

				<div className="flex shrink-0 gap-1">
					<Button
						type="button"
						variant="ghost"
						size="icon"
						className="h-8 w-8 text-muted-foreground"
						onClick={handleToggleReveal}
						disabled={isRevealing || !canWrite}
						title={canWrite ? undefined : NO_WRITE_HINT}
						aria-label={isRevealed ? "Hide values" : "Reveal values"}
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
						variant="ghost"
						size="icon"
						className="h-8 w-8"
						onClick={() => setEditOpen(true)}
						disabled={isMutating || !canWrite}
						title={canWrite ? undefined : NO_WRITE_HINT}
						aria-label={`Edit ${connector.display_name}`}
					>
						<Pencil className="h-4 w-4" />
					</Button>
					<Button
						variant="ghost"
						size="icon"
						className="h-8 w-8 text-muted-foreground hover:text-destructive"
						onClick={() => setRevertOpen(true)}
						disabled={revertDisabled}
						title={revertTitle}
						aria-label={`Revert ${connector.display_name} to default`}
					>
						<RotateCcw className="h-4 w-4" />
					</Button>
				</div>
			</CardContent>

			<ConnectorEditDialog
				connector={connector}
				open={editOpen}
				onOpenChange={setEditOpen}
				isMutating={isMutating}
				onSubmit={handleEditSubmit}
			/>

			<ConnectorRevertDialog
				connector={revertOpen ? connector : null}
				onOpenChange={setRevertOpen}
				isMutating={isMutating}
				onConfirm={handleConfirmRevert}
			/>
		</Card>
	);
}
