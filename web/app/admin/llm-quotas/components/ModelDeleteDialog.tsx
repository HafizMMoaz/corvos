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
import type { AdminLlmModelRead } from "@/contracts/types/admin-llm.types";

interface ModelDeleteDialogProps {
	/** Model pending deletion, or null when the dialog should be closed. */
	model: AdminLlmModelRead | null;
	onOpenChange: (open: boolean) => void;
	isMutating: boolean;
	onConfirm: () => void;
}

export function ModelDeleteDialog({
	model,
	onOpenChange,
	isMutating,
	onConfirm,
}: ModelDeleteDialogProps) {
	return (
		<AlertDialog open={model !== null} onOpenChange={(open) => !open && onOpenChange(open)}>
			<AlertDialogContent>
				<AlertDialogHeader>
					<AlertDialogTitle className="flex items-center gap-2">
						<ShieldAlert className="h-4 w-4 text-destructive" />
						Delete model?
					</AlertDialogTitle>
					<AlertDialogDescription>
						<span className="font-medium text-foreground">{model?.name}</span> will be permanently
						removed. This cannot be undone.
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
