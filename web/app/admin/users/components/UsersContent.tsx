"use client";

import { ChevronLeft, ChevronRight, Search } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import type { AdminUserListItemRead } from "@/contracts/types/admin-billing.types";
import { adminBillingApiService } from "@/lib/apis/admin-billing.service";
import { useAdminPermissions } from "../../admin-shell";
import { UserDetailDialog } from "./UserDetailDialog";

// PlatformPermission value, from backend/app/db.py.
const USERS_READ = "users:read";

const PAGE_SIZE = 25;

function formatBalance(micros: number): string {
	const dollars = micros / 1_000_000;
	const sign = dollars < 0 ? "-" : "";
	return `${sign}$${Math.abs(dollars).toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function formatDate(iso: string | null): string {
	if (!iso) return "-";
	return new Date(iso).toLocaleDateString(undefined, { dateStyle: "medium" });
}

export function UsersContent() {
	const { has } = useAdminPermissions();
	const canRead = has(USERS_READ);

	const [users, setUsers] = useState<AdminUserListItemRead[]>([]);
	const [total, setTotal] = useState(0);
	const [offset, setOffset] = useState(0);
	const [searchInput, setSearchInput] = useState("");
	const [searchTerm, setSearchTerm] = useState("");
	const [isLoading, setIsLoading] = useState(true);
	const [loadError, setLoadError] = useState(false);
	const [detailTarget, setDetailTarget] = useState<AdminUserListItemRead | null>(null);

	// Debounce the search box: typing shouldn't fire a request per keystroke.
	const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
	useEffect(() => {
		if (debounceRef.current) clearTimeout(debounceRef.current);
		debounceRef.current = setTimeout(() => {
			setSearchTerm(searchInput.trim());
			setOffset(0);
		}, 400);
		return () => {
			if (debounceRef.current) clearTimeout(debounceRef.current);
		};
	}, [searchInput]);

	const loadUsers = useCallback(async () => {
		setIsLoading(true);
		setLoadError(false);
		try {
			const data = await adminBillingApiService.getUsers({
				search: searchTerm || undefined,
				limit: PAGE_SIZE,
				offset,
			});
			setUsers(data.users);
			setTotal(data.total);
		} catch (error) {
			console.error("Failed to load users:", error);
			setLoadError(true);
		} finally {
			setIsLoading(false);
		}
	}, [searchTerm, offset]);

	useEffect(() => {
		if (canRead) void loadUsers();
	}, [canRead, loadUsers]);

	const pageStart = offset + 1;
	const pageEnd = Math.min(offset + PAGE_SIZE, total);
	const hasPrev = offset > 0;
	const hasNext = offset + PAGE_SIZE < total;

	if (!canRead) {
		return (
			<div className="space-y-4 min-w-0">
				<Header />
				<p className="py-6 text-center text-sm text-muted-foreground">
					Requires the <span className="font-mono">{USERS_READ}</span> permission.
				</p>
			</div>
		);
	}

	return (
		<div className="space-y-4 min-w-0">
			<Header />

			<div className="relative max-w-sm">
				<Search className="absolute top-1/2 left-2.5 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
				<Input
					value={searchInput}
					onChange={(event) => setSearchInput(event.target.value)}
					placeholder="Search by email or display name"
					className="pl-8"
					aria-label="Search users"
				/>
			</div>

			{isLoading ? (
				<div className="space-y-2">
					{["skeleton-a", "skeleton-b", "skeleton-c"].map((key) => (
						<Skeleton key={key} className="h-12 w-full" />
					))}
				</div>
			) : loadError ? (
				<Button size="sm" variant="outline" onClick={() => void loadUsers()}>
					Retry
				</Button>
			) : users.length > 0 ? (
				<div className="rounded-md border">
					<Table>
						<TableHeader>
							<TableRow>
								<TableHead>User</TableHead>
								<TableHead>Plan</TableHead>
								<TableHead>Balance</TableHead>
								<TableHead>Status</TableHead>
								<TableHead>Last login</TableHead>
							</TableRow>
						</TableHeader>
						<TableBody>
							{users.map((user) => (
								<TableRow
									key={user.id}
									className="cursor-pointer"
									onClick={() => setDetailTarget(user)}
								>
									<TableCell>
										<div className="flex flex-col">
											<span className="font-medium">{user.email}</span>
											{user.display_name && (
												<span className="text-xs text-muted-foreground">{user.display_name}</span>
											)}
										</div>
									</TableCell>
									<TableCell>
										{user.plan_name ? (
											<Badge variant="outline">{user.plan_name}</Badge>
										) : (
											<span className="text-xs text-muted-foreground">No plan</span>
										)}
									</TableCell>
									<TableCell className="text-muted-foreground">
										{formatBalance(user.credit_micros_balance)}
									</TableCell>
									<TableCell>
										{user.is_superuser ? (
											<Badge variant="secondary">Super admin</Badge>
										) : user.is_active ? (
											<Badge variant="outline">Active</Badge>
										) : (
											<Badge variant="outline" className="text-muted-foreground">
												Disabled
											</Badge>
										)}
									</TableCell>
									<TableCell className="text-muted-foreground">
										{formatDate(user.last_login)}
									</TableCell>
								</TableRow>
							))}
						</TableBody>
					</Table>
				</div>
			) : (
				<p className="py-6 text-center text-sm text-muted-foreground">
					{searchTerm ? `No users match "${searchTerm}".` : "No users yet."}
				</p>
			)}

			{total > PAGE_SIZE && (
				<div className="flex items-center justify-between">
					<p className="text-xs text-muted-foreground">
						Showing {pageStart}–{pageEnd} of {total}
					</p>
					<div className="flex gap-1">
						<Button
							variant="outline"
							size="icon"
							className="h-8 w-8"
							disabled={!hasPrev || isLoading}
							onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
							aria-label="Previous page"
						>
							<ChevronLeft className="h-4 w-4" />
						</Button>
						<Button
							variant="outline"
							size="icon"
							className="h-8 w-8"
							disabled={!hasNext || isLoading}
							onClick={() => setOffset(offset + PAGE_SIZE)}
							aria-label="Next page"
						>
							<ChevronRight className="h-4 w-4" />
						</Button>
					</div>
				</div>
			)}

			<UserDetailDialog
				user={detailTarget}
				onOpenChange={(open) => {
					if (!open) {
						setDetailTarget(null);
						// plan assignment may have changed what the list shows
						void loadUsers();
					}
				}}
			/>
		</div>
	);
}

function Header() {
	return (
		<div>
			<h4 className="text-sm font-semibold tracking-tight">Users</h4>
			<p className="text-xs text-muted-foreground">
				Search users, inspect resolved entitlements, assign plans, and grant per-user feature
				overrides.
			</p>
		</div>
	);
}
