"use client";

import { ChevronLeft, ChevronRight, Eye } from "lucide-react";
import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Pagination, PaginationContent, PaginationItem } from "@/components/ui/pagination";
import { Skeleton } from "@/components/ui/skeleton";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import type { AdminAuditLogRead } from "@/contracts/types/admin-rbac.types";
import { useAdminAuditLog } from "@/hooks/use-admin-audit-log";

function formatActor(actorUserId: string | null): string {
	if (!actorUserId) return "System";
	return actorUserId;
}

export function AuditLogContent() {
	const { entries, total, page, setPage, pageCount, pageSize, isLoading } = useAdminAuditLog();
	const [inspectEntry, setInspectEntry] = useState<AdminAuditLogRead | null>(null);

	const rangeStart = total === 0 ? 0 : page * pageSize + 1;
	const rangeEnd = Math.min((page + 1) * pageSize, total);

	return (
		<div className="space-y-6 min-w-0">
			<div>
				<h3 className="text-sm font-semibold tracking-tight">Admin audit log</h3>
				<p className="text-xs text-muted-foreground">
					Every change made through the admin dashboard, with before/after snapshots.
				</p>
			</div>

			{isLoading ? (
				<div className="space-y-2">
					{["skeleton-a", "skeleton-b", "skeleton-c", "skeleton-d"].map((key) => (
						<Skeleton key={key} className="h-12 w-full" />
					))}
				</div>
			) : entries.length > 0 ? (
				<div className="rounded-md border">
					<Table>
						<TableHeader>
							<TableRow>
								<TableHead>Action</TableHead>
								<TableHead>Target</TableHead>
								<TableHead>Actor</TableHead>
								<TableHead>When</TableHead>
								<TableHead className="text-right">Details</TableHead>
							</TableRow>
						</TableHeader>
						<TableBody>
							{entries.map((entry) => (
								<TableRow
									key={entry.id}
									className="cursor-pointer"
									onClick={() => setInspectEntry(entry)}
								>
									<TableCell>
										<Badge variant="outline" className="font-mono">
											{entry.action}
										</Badge>
									</TableCell>
									<TableCell className="max-w-[280px]">
										<div className="flex flex-col gap-0.5">
											<span className="text-sm">{entry.target_type}</span>
											{entry.target_id && (
												<span className="truncate font-mono text-xs text-muted-foreground">
													{entry.target_id}
												</span>
											)}
										</div>
									</TableCell>
									<TableCell className="font-mono text-xs text-muted-foreground">
										{formatActor(entry.actor_user_id)}
									</TableCell>
									<TableCell className="whitespace-nowrap text-xs text-muted-foreground">
										{new Date(entry.created_at).toLocaleString()}
									</TableCell>
									<TableCell className="text-right">
										<Button
											variant="ghost"
											size="icon"
											className="h-8 w-8"
											onClick={(event) => {
												event.stopPropagation();
												setInspectEntry(entry);
											}}
										>
											<Eye className="h-4 w-4" />
										</Button>
									</TableCell>
								</TableRow>
							))}
						</TableBody>
					</Table>
				</div>
			) : (
				<p className="py-6 text-center text-sm text-muted-foreground">No audit log entries yet.</p>
			)}

			{total > 0 && (
				<div className="flex items-center justify-between gap-4">
					<p className="text-sm text-muted-foreground">
						<span className="text-foreground">
							{rangeStart}-{rangeEnd}
						</span>{" "}
						of <span className="text-foreground">{total}</span>
					</p>
					<Pagination className="mx-0 w-auto justify-end">
						<PaginationContent>
							<PaginationItem>
								<Button
									size="icon"
									variant="outline"
									onClick={() => setPage((current) => Math.max(0, current - 1))}
									disabled={page <= 0}
								>
									<ChevronLeft className="h-4 w-4" />
								</Button>
							</PaginationItem>
							<PaginationItem>
								<span className="px-2 text-sm text-muted-foreground">
									Page {page + 1} of {pageCount}
								</span>
							</PaginationItem>
							<PaginationItem>
								<Button
									size="icon"
									variant="outline"
									onClick={() => setPage((current) => Math.min(pageCount - 1, current + 1))}
									disabled={page >= pageCount - 1}
								>
									<ChevronRight className="h-4 w-4" />
								</Button>
							</PaginationItem>
						</PaginationContent>
					</Pagination>
				</div>
			)}

			<Dialog open={inspectEntry !== null} onOpenChange={(open) => !open && setInspectEntry(null)}>
				<DialogContent className="max-w-2xl">
					<DialogHeader>
						<DialogTitle className="font-mono">{inspectEntry?.action}</DialogTitle>
						<DialogDescription>
							{inspectEntry?.target_type}
							{inspectEntry?.target_id ? ` · ${inspectEntry.target_id}` : ""} ·{" "}
							{inspectEntry ? new Date(inspectEntry.created_at).toLocaleString() : ""}
						</DialogDescription>
					</DialogHeader>

					<div className="grid gap-4 sm:grid-cols-2">
						<div className="space-y-1.5">
							<p className="text-xs font-medium text-muted-foreground">Before</p>
							<pre className="max-h-64 overflow-auto rounded-md border bg-muted/50 p-3 text-xs">
								{JSON.stringify(inspectEntry?.before ?? null, null, 2)}
							</pre>
						</div>
						<div className="space-y-1.5">
							<p className="text-xs font-medium text-muted-foreground">After</p>
							<pre className="max-h-64 overflow-auto rounded-md border bg-muted/50 p-3 text-xs">
								{JSON.stringify(inspectEntry?.after ?? null, null, 2)}
							</pre>
						</div>
					</div>

					{inspectEntry?.extra_metadata && (
						<div className="space-y-1.5">
							<p className="text-xs font-medium text-muted-foreground">Metadata</p>
							<pre className="max-h-40 overflow-auto rounded-md border bg-muted/50 p-3 text-xs">
								{JSON.stringify(inspectEntry.extra_metadata, null, 2)}
							</pre>
						</div>
					)}
				</DialogContent>
			</Dialog>
		</div>
	);
}
