"use client";

import { ShieldAlert } from "lucide-react";
import {
	AlertDialog,
	AlertDialogAction,
	AlertDialogCancel,
	AlertDialogContent,
	AlertDialogDescription,
	AlertDialogFooter,
	AlertDialogHeader,
	AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Spinner } from "@/components/ui/spinner";
import type { AdminConnectorCredentialRead } from "@/contracts/types/admin-connectors.types";

interface ConnectorRevertDialogProps {
	/** Connector pending revert-to-default, or null when the dialog should be closed. */
	connector: AdminConnectorCredentialRead | null;
	onOpenChange: (open: boolean) => void;
	isMutating: boolean;
	onConfirm: () => void;
}

/**
 * Confirm dialog for reverting a connector's stored credentials back to its
 * environment-variable default. Own small dedicated dialog rather than a
 * cross-import from the settings feature folder, following the llm-quotas
 * track's precedent (`ProviderDeleteDialog.tsx`, `QuotaResetConfirmDialog.tsx`).
 */
export function ConnectorRevertDialog({
	connector,
	onOpenChange,
	isMutating,
	onConfirm,
}: ConnectorRevertDialogProps) {
	return (
		<AlertDialog open={connector !== null} onOpenChange={(open) => !open && onOpenChange(open)}>
			<AlertDialogContent>
				<AlertDialogHeader>
					<AlertDialogTitle className="flex items-center gap-2">
						<ShieldAlert className="h-4 w-4 text-destructive" />
						Revert to default?
					</AlertDialogTitle>
					<AlertDialogDescription>
						Revert <span className="font-medium text-foreground">{connector?.display_name}</span> to
						default? This removes the stored client ID and secret; the connector will use its
						environment-variable default (if any) until reconfigured. This cannot be undone.
					</AlertDialogDescription>
				</AlertDialogHeader>
				<AlertDialogFooter>
					<AlertDialogCancel disabled={isMutating}>Cancel</AlertDialogCancel>
					<AlertDialogAction
						disabled={isMutating}
						className="bg-destructive text-white hover:bg-destructive/90"
						onClick={(event) => {
							event.preventDefault();
							onConfirm();
						}}
					>
						{isMutating ? (
							<span className="inline-flex items-center gap-2">
								<Spinner size="xs" />
								Reverting...
							</span>
						) : (
							"Revert"
						)}
					</AlertDialogAction>
				</AlertDialogFooter>
			</AlertDialogContent>
		</AlertDialog>
	);
}
