"use client";

import { Eye, EyeOff } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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
import type {
	AdminConnectorCredentialRead,
	UpdateConnectorCredentialRequest,
} from "@/contracts/types/admin-connectors.types";

interface ConnectorEditDialogProps {
	connector: AdminConnectorCredentialRead;
	open: boolean;
	onOpenChange: (open: boolean) => void;
	isMutating: boolean;
	/**
	 * Called on Save with a partial-update payload built via real key
	 * omission (an unchanged field is a genuinely absent key, not an
	 * explicit `undefined`). The caller owns closing the dialog.
	 */
	onSubmit: (payload: UpdateConnectorCredentialRequest) => void;
}

type FieldAction = "unchanged" | "set" | "clear";

function resolveAction(draft: string, clearChecked: boolean): FieldAction {
	if (clearChecked) return "clear";
	if (draft.trim() !== "") return "set";
	return "unchanged";
}

/**
 * Edit dialog for a connector's client_id/client_secret pair plus its
 * is_enabled toggle. Unlike SettingEditDialog (one value, unconditional
 * overwrite), this dialog has real partial-update semantics: each secret
 * field starts blank (there is no current value to pre-fill, only a
 * has_client_id/has_client_secret boolean) and independently tracks whether
 * the user left it alone, typed a new value, or explicitly cleared it.
 */
export function ConnectorEditDialog({
	connector,
	open,
	onOpenChange,
	isMutating,
	onSubmit,
}: ConnectorEditDialogProps) {
	const isComposio = connector.connector_key === "composio";
	const clientIdId = `connector-client-id-${connector.connector_key}`;
	const clientSecretId = `connector-client-secret-${connector.connector_key}`;
	const enabledId = `connector-enabled-${connector.connector_key}`;

	const [draftClientId, setDraftClientId] = useState("");
	const [clearClientId, setClearClientId] = useState(false);
	const [showClientId, setShowClientId] = useState(false);

	const [draftClientSecret, setDraftClientSecret] = useState("");
	const [clearClientSecret, setClearClientSecret] = useState(false);
	const [showClientSecret, setShowClientSecret] = useState(false);

	const [draftEnabled, setDraftEnabled] = useState(connector.is_enabled);

	// Reset the draft every time the dialog opens for this connector -- secret
	// fields always start blank (only a has_client_id/has_client_secret
	// boolean is known, never a value), is_enabled starts from the current
	// known value.
	useEffect(() => {
		if (!open) return;
		setDraftClientId("");
		setClearClientId(false);
		setShowClientId(false);
		setDraftClientSecret("");
		setClearClientSecret(false);
		setShowClientSecret(false);
		setDraftEnabled(connector.is_enabled);
	}, [open, connector.is_enabled]);

	const clientIdAction: FieldAction = isComposio
		? "unchanged"
		: resolveAction(draftClientId, clearClientId);
	const clientSecretAction: FieldAction = resolveAction(draftClientSecret, clearClientSecret);

	// `is_enabled` gets the same "only send what genuinely changed" discipline
	// as the two credential fields: sending it unconditionally meant opening
	// this dialog on an unconfigured connector and hitting Save with no edits
	// still PUT a non-empty body, which makes the backend create an override
	// row with both credential columns NULL -- flipping the card from an
	// accurate "No override - using environment default" to a misleading
	// "Updated ... by ...", plus an audit entry for a change that never
	// happened.
	const enabledChanged = draftEnabled !== connector.is_enabled;

	const hasChanges =
		enabledChanged || clientIdAction !== "unchanged" || clientSecretAction !== "unchanged";

	function handleSubmit() {
		const payload: UpdateConnectorCredentialRequest = {};
		// Values are trimmed here, matching the trim `resolveAction` already
		// applies when deciding whether a field was really edited, so a
		// stray-whitespace paste never reaches the vault.
		if (clientIdAction === "set") payload.client_id = draftClientId.trim();
		else if (clientIdAction === "clear") payload.client_id = null;
		// "unchanged" -> key stays absent entirely

		if (clientSecretAction === "set") payload.client_secret = draftClientSecret.trim();
		else if (clientSecretAction === "clear") payload.client_secret = null;

		if (enabledChanged) payload.is_enabled = draftEnabled;

		onSubmit(payload);
	}

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent>
				<DialogHeader>
					<DialogTitle>{connector.display_name}</DialogTitle>
					<DialogDescription>
						{connector.description || "Update this connector's OAuth app credentials."}
					</DialogDescription>
				</DialogHeader>

				<div className="space-y-4">
					{!isComposio && (
						<div className="space-y-2">
							<Label htmlFor={clientIdId}>Client ID</Label>
							<div className="relative">
								<Input
									id={clientIdId}
									value={draftClientId}
									onChange={(event) => setDraftClientId(event.target.value)}
									placeholder={
										connector.has_client_id ? "Leave blank to keep the current value" : "Not set"
									}
									type={showClientId ? "text" : "password"}
									className="pr-11"
									disabled={isMutating || clearClientId}
								/>
								<Button
									type="button"
									variant="ghost"
									size="icon"
									className="absolute top-1/2 right-1 size-8 -translate-y-1/2 text-muted-foreground"
									onClick={() => setShowClientId((current) => !current)}
									disabled={!draftClientId}
									aria-label={showClientId ? "Hide value" : "Show value"}
								>
									{showClientId ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
								</Button>
							</div>
							{connector.has_client_id && (
								<div className="flex items-center gap-2">
									<Checkbox
										id={`${clientIdId}-clear`}
										checked={clearClientId}
										onCheckedChange={(checked) => setClearClientId(!!checked)}
										disabled={isMutating}
									/>
									<Label htmlFor={`${clientIdId}-clear`} className="font-normal">
										Clear the stored client ID
									</Label>
								</div>
							)}
						</div>
					)}

					<div className="space-y-2">
						<Label htmlFor={clientSecretId}>Client Secret</Label>
						<div className="relative">
							<Input
								id={clientSecretId}
								value={draftClientSecret}
								onChange={(event) => setDraftClientSecret(event.target.value)}
								placeholder={
									connector.has_client_secret ? "Leave blank to keep the current value" : "Not set"
								}
								type={showClientSecret ? "text" : "password"}
								className="pr-11"
								disabled={isMutating || clearClientSecret}
							/>
							<Button
								type="button"
								variant="ghost"
								size="icon"
								className="absolute top-1/2 right-1 size-8 -translate-y-1/2 text-muted-foreground"
								onClick={() => setShowClientSecret((current) => !current)}
								disabled={!draftClientSecret}
								aria-label={showClientSecret ? "Hide value" : "Show value"}
							>
								{showClientSecret ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
							</Button>
						</div>
						{connector.has_client_secret && (
							<div className="flex items-center gap-2">
								<Checkbox
									id={`${clientSecretId}-clear`}
									checked={clearClientSecret}
									onCheckedChange={(checked) => setClearClientSecret(!!checked)}
									disabled={isMutating}
								/>
								<Label htmlFor={`${clientSecretId}-clear`} className="font-normal">
									Clear the stored client secret
								</Label>
							</div>
						)}
					</div>

					<div className="flex items-center gap-2">
						<Switch
							id={enabledId}
							checked={draftEnabled}
							onCheckedChange={setDraftEnabled}
							disabled={isMutating}
						/>
						<Label htmlFor={enabledId} className="font-normal">
							{draftEnabled ? "Enabled" : "Disabled"}
						</Label>
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
						size="sm"
						disabled={isMutating || !hasChanges}
						onClick={handleSubmit}
						title={hasChanges ? undefined : "Nothing to save - no field has been changed"}
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
