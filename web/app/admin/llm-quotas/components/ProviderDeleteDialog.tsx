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
import type { AdminLlmProviderRead } from "@/contracts/types/admin-llm.types";

interface ProviderDeleteDialogProps {
	/** Provider pending deletion, or null when the dialog should be closed. */
	provider: AdminLlmProviderRead | null;
	onOpenChange: (open: boolean) => void;
	isMutating: boolean;
	onConfirm: () => void;
}

/**
 * Delete confirm for a provider. Deletion cascades to every model built on
 * top of it, so the copy calls that out explicitly rather than just warning
 * "cannot be undone" the way a plain resource delete would.
 */
export function ProviderDeleteDialog({
	provider,
	onOpenChange,
	isMutating,
	onConfirm,
}: ProviderDeleteDialogProps) {
	return (
		<AlertDialog open={provider !== null} onOpenChange={(open) => !open && onOpenChange(open)}>
			<AlertDialogContent>
				<AlertDialogHeader>
					<AlertDialogTitle className="flex items-center gap-2">
						<ShieldAlert className="h-4 w-4 text-destructive" />
						Delete provider?
					</AlertDialogTitle>
					<AlertDialogDescription>
						<span className="font-medium text-foreground">{provider?.display_name}</span> will be
						permanently removed, along with every model configured under it. This cannot be undone.
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
								Deleting...
							</span>
						) : (
							"Delete"
						)}
					</AlertDialogAction>
				</AlertDialogFooter>
			</AlertDialogContent>
		</AlertDialog>
	);
}
