"use client";

import { ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";
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

interface QuotaResetConfirmDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	isMutating: boolean;
	title: ReactNode;
	description: ReactNode;
	onConfirm: () => void;
}

/**
 * Shared confirm/cancel AlertDialog for both quota reset flows -- the
 * platform-wide reset and the per-user reset. Only the copy and confirm
 * action differ between the two call sites.
 */
export function QuotaResetConfirmDialog({
	open,
	onOpenChange,
	isMutating,
	title,
	description,
	onConfirm,
}: QuotaResetConfirmDialogProps) {
	return (
		<AlertDialog open={open} onOpenChange={onOpenChange}>
			<AlertDialogContent>
				<AlertDialogHeader>
					<AlertDialogTitle className="flex items-center gap-2">
						<ShieldAlert className="h-4 w-4 text-destructive" />
						{title}
					</AlertDialogTitle>
					<AlertDialogDescription>{description}</AlertDialogDescription>
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
								Resetting...
							</span>
						) : (
							"Reset"
						)}
					</AlertDialogAction>
				</AlertDialogFooter>
			</AlertDialogContent>
		</AlertDialog>
	);
}
