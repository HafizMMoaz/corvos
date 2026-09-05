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
import type { FeatureFlagRead } from "@/contracts/types/admin-billing.types";

interface FeatureFlagDeleteDialogProps {
	/** Flag pending deletion, or null when the dialog should be closed. */
	flag: FeatureFlagRead | null;
	onOpenChange: (open: boolean) => void;
	isMutating: boolean;
	onConfirm: () => void;
}

/**
 * Delete confirm for a feature flag. Deleting cascades to every
 * `plan_feature_values` / `user_feature_overrides` row referencing it, so the
 * copy calls that out instead of a generic "cannot be undone".
 */
export function FeatureFlagDeleteDialog({
	flag,
	onOpenChange,
	isMutating,
	onConfirm,
}: FeatureFlagDeleteDialogProps) {
	return (
		<AlertDialog open={flag !== null} onOpenChange={(open) => !open && onOpenChange(open)}>
			<AlertDialogContent>
				<AlertDialogHeader>
					<AlertDialogTitle className="flex items-center gap-2">
						<ShieldAlert className="h-4 w-4 text-destructive" />
						Delete feature flag?
					</AlertDialogTitle>
					<AlertDialogDescription>
						<span className="font-medium text-foreground">{flag?.name}</span> will be permanently
						removed, along with every plan value and user override configured for it. This cannot be
						undone.
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
