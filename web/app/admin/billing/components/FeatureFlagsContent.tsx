"use client";

import { Pencil, Trash2 } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import type { FeatureFlagRead } from "@/contracts/types/admin-billing.types";
import { useAdminBilling } from "@/hooks/use-admin-billing";
import { useAdminPermissions } from "../../admin-shell";
import { FeatureFlagDeleteDialog } from "./FeatureFlagDeleteDialog";
import { FeatureFlagFormDialog } from "./FeatureFlagFormDialog";

// PlatformPermission values, from backend/app/db.py.
const FEATURE_FLAGS_WRITE = "feature_flags:write";
const NO_WRITE_HINT = "Requires the feature_flags:write permission";

export function FeatureFlagsContent() {
	const {
		featureFlags,
		isLoading,
		isMutating,
		createFeatureFlag,
		updateFeatureFlag,
		deleteFeatureFlag,
	} = useAdminBilling();
	const { has } = useAdminPermissions();
	const canWrite = has(FEATURE_FLAGS_WRITE);

	const [formOpen, setFormOpen] = useState(false);
	const [editingFlag, setEditingFlag] = useState<FeatureFlagRead | null>(null);
	const [deleteTarget, setDeleteTarget] = useState<FeatureFlagRead | null>(null);

	function openCreateDialog() {
		setEditingFlag(null);
		setFormOpen(true);
	}

	function openEditDialog(flag: FeatureFlagRead) {
		setEditingFlag(flag);
		setFormOpen(true);
	}

	return (
		<div className="space-y-4 min-w-0">
			<div className="flex items-center justify-between gap-3">
				<div>
					<h4 className="text-sm font-semibold tracking-tight">Feature flags</h4>
					<p className="text-xs text-muted-foreground">
						The feature vocabulary plans can enable. Each plan turns flags on via its entitlements
						dialog; users can get individual overrides in Users.
					</p>
				</div>
				<Button
					size="sm"
					className="shrink-0"
					onClick={openCreateDialog}
					disabled={!canWrite}
					title={canWrite ? undefined : NO_WRITE_HINT}
				>
					Add flag
				</Button>
			</div>

			{isLoading ? (
				<div className="space-y-2">
					{["skeleton-a", "skeleton-b", "skeleton-c"].map((key) => (
						<Skeleton key={key} className="h-12 w-full" />
					))}
				</div>
			) : featureFlags.length > 0 ? (
				<div className="rounded-md border">
					<Table>
						<TableHeader>
							<TableRow>
								<TableHead>Flag</TableHead>
								<TableHead>Description</TableHead>
								<TableHead className="text-right">Actions</TableHead>
							</TableRow>
						</TableHeader>
						<TableBody>
							{featureFlags.map((flag) => (
								<TableRow key={flag.id}>
									<TableCell>
										<div className="flex flex-col">
											<span className="font-medium">{flag.name}</span>
											<span className="font-mono text-xs text-muted-foreground">
												{flag.flag_key}
											</span>
										</div>
									</TableCell>
									<TableCell className="max-w-[280px] text-muted-foreground">
										{flag.description ?? "-"}
									</TableCell>
									<TableCell className="text-right">
										<div className="flex justify-end gap-1">
											<Button
												variant="ghost"
												size="icon"
												className="h-8 w-8"
												onClick={() => openEditDialog(flag)}
												disabled={!canWrite}
												title={canWrite ? undefined : NO_WRITE_HINT}
												aria-label={`Edit ${flag.name}`}
											>
												<Pencil className="h-4 w-4" />
											</Button>
											<Button
												variant="ghost"
												size="icon"
												className="h-8 w-8 text-muted-foreground hover:text-destructive"
												onClick={() => setDeleteTarget(flag)}
												disabled={!canWrite}
												title={canWrite ? undefined : NO_WRITE_HINT}
												aria-label={`Delete ${flag.name}`}
											>
												<Trash2 className="h-4 w-4" />
											</Button>
										</div>
									</TableCell>
								</TableRow>
							))}
						</TableBody>
					</Table>
				</div>
			) : (
				<p className="py-6 text-center text-sm text-muted-foreground">
					No feature flags defined yet. Flags are the feature vocabulary plans switch on.
				</p>
			)}

			<FeatureFlagFormDialog
				open={formOpen}
				onOpenChange={setFormOpen}
				flag={editingFlag}
				isMutating={isMutating}
				onCreate={createFeatureFlag}
				onUpdate={updateFeatureFlag}
			/>

			<FeatureFlagDeleteDialog
				flag={deleteTarget}
				onOpenChange={(open) => !open && setDeleteTarget(null)}
				isMutating={isMutating}
				onConfirm={async () => {
					if (!deleteTarget) return;
					await deleteFeatureFlag(deleteTarget.id);
					setDeleteTarget(null);
				}}
			/>
		</div>
	);
}
