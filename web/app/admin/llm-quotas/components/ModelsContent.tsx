"use client";

import { Pencil, RefreshCw, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";
import { Badge } from "@/components/ui/badge";
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
import type { AdminLlmModelRead } from "@/contracts/types/admin-llm.types";
import { useAdminLlmModels } from "@/hooks/use-admin-llm-models";
import { useAdminLlmProviders } from "@/hooks/use-admin-llm-providers";
import { useAdminPermissions } from "../../admin-shell";
import { ModelDeleteDialog } from "./ModelDeleteDialog";
import { ModelFormDialog } from "./ModelFormDialog";

// PlatformPermission values, from backend/app/db.py.
const LLM_PROVIDERS_WRITE = "llm_providers:write";
const NO_WRITE_HINT = "Requires the llm_providers:write permission";

export function ModelsContent() {
	const { models, isLoading, isMutating, createModel, updateModel, deleteModel, reloadCatalog } =
		useAdminLlmModels();
	const { providers } = useAdminLlmProviders();
	const { has } = useAdminPermissions();
	const canWrite = has(LLM_PROVIDERS_WRITE);

	const [formOpen, setFormOpen] = useState(false);
	const [editingModel, setEditingModel] = useState<AdminLlmModelRead | null>(null);
	const [deleteTarget, setDeleteTarget] = useState<AdminLlmModelRead | null>(null);

	const providerNameById = useMemo(() => {
		const map = new Map<number, string>();
		for (const provider of providers) map.set(provider.id, provider.display_name);
		return map;
	}, [providers]);

	const sortedModels = useMemo(
		() => [...models].sort((a, b) => a.name.localeCompare(b.name)),
		[models]
	);

	function openCreateDialog() {
		setEditingModel(null);
		setFormOpen(true);
	}

	function openEditDialog(model: AdminLlmModelRead) {
		setEditingModel(model);
		setFormOpen(true);
	}

	return (
		<div className="space-y-4 min-w-0">
			<div className="flex items-center justify-between gap-3">
				<div>
					<h4 className="text-sm font-semibold tracking-tight">Models</h4>
					<p className="text-xs text-muted-foreground">
						Models built on top of a configured provider, exposed through the platform's model
						catalog.
					</p>
				</div>
				<div className="flex shrink-0 gap-2">
					<Button
						size="sm"
						variant="outline"
						onClick={() => void reloadCatalog()}
						disabled={!canWrite || isMutating}
						title={canWrite ? undefined : NO_WRITE_HINT}
					>
						<RefreshCw className="h-4 w-4" />
						Reload catalog
					</Button>
					<Button
						size="sm"
						onClick={openCreateDialog}
						disabled={!canWrite || providers.length === 0}
						title={
							!canWrite
								? NO_WRITE_HINT
								: providers.length === 0
									? "Add a provider first"
									: undefined
						}
					>
						Add model
					</Button>
				</div>
			</div>

			{isLoading ? (
				<div className="space-y-2">
					{["skeleton-a", "skeleton-b", "skeleton-c"].map((key) => (
						<Skeleton key={key} className="h-12 w-full" />
					))}
				</div>
			) : sortedModels.length > 0 ? (
				<div className="rounded-md border">
					<Table>
						<TableHeader>
							<TableRow>
								<TableHead>Model</TableHead>
								<TableHead>Provider</TableHead>
								<TableHead>Billing tier</TableHead>
								<TableHead>Status</TableHead>
								<TableHead className="text-right">Actions</TableHead>
							</TableRow>
						</TableHeader>
						<TableBody>
							{sortedModels.map((model) => (
								<TableRow key={model.id}>
									<TableCell>
										<div className="flex flex-col">
											<span className="font-medium">{model.name}</span>
											<span className="font-mono text-xs text-muted-foreground">
												{model.model_name}
											</span>
										</div>
									</TableCell>
									<TableCell className="text-muted-foreground">
										{providerNameById.get(model.provider_id) ?? `#${model.provider_id}`}
									</TableCell>
									<TableCell>
										<Badge variant={model.billing_tier === "free" ? "secondary" : "outline"}>
											{model.billing_tier}
										</Badge>
									</TableCell>
									<TableCell>
										{model.is_enabled ? (
											<Badge variant="secondary">Enabled</Badge>
										) : (
											<Badge variant="outline">Disabled</Badge>
										)}
									</TableCell>
									<TableCell className="text-right">
										<div className="flex justify-end gap-1">
											<Button
												variant="ghost"
												size="icon"
												className="h-8 w-8"
												onClick={() => openEditDialog(model)}
												disabled={!canWrite}
												title={canWrite ? undefined : NO_WRITE_HINT}
												aria-label={`Edit ${model.name}`}
											>
												<Pencil className="h-4 w-4" />
											</Button>
											<Button
												variant="ghost"
												size="icon"
												className="h-8 w-8 text-muted-foreground hover:text-destructive"
												onClick={() => setDeleteTarget(model)}
												disabled={!canWrite}
												title={canWrite ? undefined : NO_WRITE_HINT}
												aria-label={`Delete ${model.name}`}
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
				<p className="py-6 text-center text-sm text-muted-foreground">No models configured yet.</p>
			)}

			<ModelFormDialog
				open={formOpen}
				onOpenChange={setFormOpen}
				model={editingModel}
				providers={providers}
				isMutating={isMutating}
				onCreate={createModel}
				onUpdate={updateModel}
			/>

			<ModelDeleteDialog
				model={deleteTarget}
				onOpenChange={(open) => !open && setDeleteTarget(null)}
				isMutating={isMutating}
				onConfirm={async () => {
					if (!deleteTarget) return;
					await deleteModel(deleteTarget.id);
					setDeleteTarget(null);
				}}
			/>
		</div>
	);
}
