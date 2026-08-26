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

interface SettingConfirmDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	isMutating: boolean;
	title: ReactNode;
	description: ReactNode;
	confirmLabel: string;
	pendingLabel: string;
	showShieldIcon?: boolean;
	onConfirm: () => void;
}

/**
 * Shared confirm/cancel AlertDialog, reused per-row for both the
 * revert-to-default flow and the disruptive-change-update flow - only the
 * copy and confirm action differ between the two.
 */
export function SettingConfirmDialog({
	open,
	onOpenChange,
	isMutating,
	title,
	description,
	confirmLabel,
	pendingLabel,
	showShieldIcon = false,
	onConfirm,
}: SettingConfirmDialogProps) {
	return (
		<AlertDialog open={open} onOpenChange={onOpenChange}>
			<AlertDialogContent>
				<AlertDialogHeader>
					<AlertDialogTitle className="flex items-center gap-2">
						{showShieldIcon && <ShieldAlert className="h-4 w-4 text-destructive" />}
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
								{pendingLabel}
							</span>
						) : (
							confirmLabel
						)}
					</AlertDialogAction>
				</AlertDialogFooter>
			</AlertDialogContent>
		</AlertDialog>
	);
}
