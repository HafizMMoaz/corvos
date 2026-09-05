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
import type { PlanRead } from "@/contracts/types/admin-billing.types";

interface PlanDeleteDialogProps {
	/** Plan pending deletion, or null when the dialog should be closed. */
	plan: PlanRead | null;
	onOpenChange: (open: boolean) => void;
	isMutating: boolean;
	onConfirm: () => void;
}

/**
 * Delete confirm for a plan. `User.plan_id` is ON DELETE SET NULL, so the
 * copy calls out that members fall back to "no plan" (unrestricted models,
 * every flag off) rather than blocking the delete.
 */
export function PlanDeleteDialog({
	plan,
	onOpenChange,
	isMutating,
	onConfirm,
}: PlanDeleteDialogProps) {
	return (
		<AlertDialog open={plan !== null} onOpenChange={(open) => !open && onOpenChange(open)}>
			<AlertDialogContent>
				<AlertDialogHeader>
					<AlertDialogTitle className="flex items-center gap-2">
						<ShieldAlert className="h-4 w-4 text-destructive" />
						Delete plan?
					</AlertDialogTitle>
					<AlertDialogDescription>
						<span className="font-medium text-foreground">{plan?.name}</span> will be permanently
						removed. Users currently on it are un-assigned and fall back to "no plan" (unrestricted
						model access, every feature flag off). Consider deactivating instead to retire it
						without orphaning members. This cannot be undone.
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
