"use client";

import { Eye, Pencil, Trash2 } from "lucide-react";
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
import type { AdminLlmProviderRead } from "@/contracts/types/admin-llm.types";
import { useAdminLlmProviders } from "@/hooks/use-admin-llm-providers";
import { useAdminPermissions } from "../../admin-shell";
import { ProviderDeleteDialog } from "./ProviderDeleteDialog";
import { ProviderFormDialog } from "./ProviderFormDialog";
import { ProviderRevealDialog } from "./ProviderRevealDialog";

// PlatformPermission values, from backend/app/db.py. There is no separate
// reveal permission for this catalog: llm_providers:write gates create,
// edit, delete, and reveal alike.
const LLM_PROVIDERS_WRITE = "llm_providers:write";
const NO_WRITE_HINT = "Requires the llm_providers:write permission";

export function ProvidersContent() {
	const {
		providers,
		isLoading,
		isMutating,
		createProvider,
		updateProvider,
		deleteProvider,
		revealProviderApiKey,
	} = useAdminLlmProviders();
	const { has } = useAdminPermissions();
	const canWrite = has(LLM_PROVIDERS_WRITE);

	const [formOpen, setFormOpen] = useState(false);
	const [editingProvider, setEditingProvider] = useState<AdminLlmProviderRead | null>(null);
	const [deleteTarget, setDeleteTarget] = useState<AdminLlmProviderRead | null>(null);
	const [revealTarget, setRevealTarget] = useState<AdminLlmProviderRead | null>(null);

	const sortedProviders = useMemo(
		() => [...providers].sort((a, b) => a.provider_key.localeCompare(b.provider_key)),
		[providers]
	);

	function openCreateDialog() {
		setEditingProvider(null);
		setFormOpen(true);
	}

	function openEditDialog(provider: AdminLlmProviderRead) {
		setEditingProvider(provider);
		setFormOpen(true);
	}

	return (
		<div className="space-y-4 min-w-0">
			<div className="flex items-center justify-between gap-3">
				<div>
					<h4 className="text-sm font-semibold tracking-tight">Providers</h4>
					<p className="text-xs text-muted-foreground">
						Connections to upstream LLM providers. Deleting a provider also deletes every model
						built on top of it.
					</p>
				</div>
				<Button
					size="sm"
					onClick={openCreateDialog}
					disabled={!canWrite}
					title={canWrite ? undefined : NO_WRITE_HINT}
				>
					Add provider
				</Button>
			</div>

			{isLoading ? (
				<div className="space-y-2">
					{["skeleton-a", "skeleton-b", "skeleton-c"].map((key) => (
						<Skeleton key={key} className="h-12 w-full" />
					))}
				</div>
			) : sortedProviders.length > 0 ? (
				<div className="rounded-md border">
					<Table>
						<TableHeader>
							<TableRow>
								<TableHead>Provider</TableHead>
								<TableHead>Transport</TableHead>
								<TableHead>Auth style</TableHead>
								<TableHead>API key</TableHead>
								<TableHead>Status</TableHead>
								<TableHead className="text-right">Actions</TableHead>
							</TableRow>
						</TableHeader>
						<TableBody>
							{sortedProviders.map((provider) => (
								<TableRow key={provider.id}>
									<TableCell>
										<div className="flex flex-col">
											<span className="font-medium">{provider.display_name}</span>
											<span className="font-mono text-xs text-muted-foreground">
												{provider.provider_key}
											</span>
										</div>
									</TableCell>
									<TableCell className="text-muted-foreground">{provider.transport}</TableCell>
									<TableCell className="text-muted-foreground">{provider.auth_style}</TableCell>
									<TableCell>
										{provider.has_api_key ? (
											<Badge variant="secondary">Key set</Badge>
										) : (
											<Badge variant="outline">No key</Badge>
										)}
									</TableCell>
									<TableCell>
										{provider.is_enabled ? (
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
												onClick={() => setRevealTarget(provider)}
												disabled={!canWrite || !provider.has_api_key}
												title={
													!canWrite
														? NO_WRITE_HINT
														: !provider.has_api_key
															? "No API key stored"
															: "Reveal API key"
												}
												aria-label={`Reveal API key for ${provider.display_name}`}
											>
												<Eye className="h-4 w-4" />
											</Button>
											<Button
												variant="ghost"
												size="icon"
												className="h-8 w-8"
												onClick={() => openEditDialog(provider)}
												disabled={!canWrite}
												title={canWrite ? undefined : NO_WRITE_HINT}
												aria-label={`Edit ${provider.display_name}`}
											>
												<Pencil className="h-4 w-4" />
											</Button>
											<Button
												variant="ghost"
												size="icon"
												className="h-8 w-8 text-muted-foreground hover:text-destructive"
												onClick={() => setDeleteTarget(provider)}
												disabled={!canWrite}
												title={canWrite ? undefined : NO_WRITE_HINT}
												aria-label={`Delete ${provider.display_name}`}
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
					No providers configured yet.
				</p>
			)}

			<ProviderFormDialog
				open={formOpen}
				onOpenChange={setFormOpen}
				provider={editingProvider}
				isMutating={isMutating}
				onCreate={createProvider}
				onUpdate={updateProvider}
			/>

			<ProviderDeleteDialog
				provider={deleteTarget}
				onOpenChange={(open) => !open && setDeleteTarget(null)}
				isMutating={isMutating}
				onConfirm={async () => {
					if (!deleteTarget) return;
					await deleteProvider(deleteTarget.id);
					setDeleteTarget(null);
				}}
			/>

			<ProviderRevealDialog
				provider={revealTarget}
				onOpenChange={(open) => !open && setRevealTarget(null)}
				onReveal={revealProviderApiKey}
			/>
		</div>
	);
}
