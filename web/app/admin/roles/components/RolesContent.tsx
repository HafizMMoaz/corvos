"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Pencil, ShieldAlert, Trash2 } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import {
	Form,
	FormControl,
	FormField,
	FormItem,
	FormLabel,
	FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";
import type { PlatformRoleRead } from "@/contracts/types/admin-rbac.types";
import { useAdminRoles } from "@/hooks/use-admin-roles";

const roleFormSchema = z.object({
	name: z.string().min(1, "Name is required").max(100, "Name must be 100 characters or fewer"),
	description: z.string().max(500, "Description must be 500 characters or fewer").optional(),
	permissions: z.array(z.string()).min(1, "Select at least one permission"),
});

type RoleFormValues = z.infer<typeof roleFormSchema>;

const EMPTY_FORM_VALUES: RoleFormValues = {
	name: "",
	description: "",
	permissions: [],
};

export function RolesContent() {
	const { roles, permissions, isLoading, isMutating, createRole, updateRole, deleteRole } =
		useAdminRoles();

	const [formOpen, setFormOpen] = useState(false);
	const [editingRole, setEditingRole] = useState<PlatformRoleRead | null>(null);
	const [deleteTarget, setDeleteTarget] = useState<PlatformRoleRead | null>(null);

	const form = useForm<RoleFormValues>({
		resolver: zodResolver(roleFormSchema),
		defaultValues: EMPTY_FORM_VALUES,
	});

	const sortedRoles = useMemo(
		() => [...roles].sort((a, b) => a.name.localeCompare(b.name)),
		[roles]
	);

	const openCreateDialog = () => {
		setEditingRole(null);
		form.reset(EMPTY_FORM_VALUES);
		setFormOpen(true);
	};

	const openEditDialog = (role: PlatformRoleRead) => {
		setEditingRole(role);
		form.reset({
			name: role.name,
			description: role.description ?? "",
			permissions: role.permissions,
		});
		setFormOpen(true);
	};

	useEffect(() => {
		if (!formOpen) {
			setEditingRole(null);
			form.reset(EMPTY_FORM_VALUES);
		}
	}, [formOpen, form.reset]);

	const handleSubmit = async (values: RoleFormValues) => {
		const payload = {
			name: values.name,
			description: values.description?.trim() ? values.description.trim() : undefined,
			permissions: values.permissions,
		};

		if (editingRole) {
			await updateRole(editingRole.id, payload);
		} else {
			await createRole(payload);
		}
		setFormOpen(false);
	};

	const handleConfirmDelete = async () => {
		if (!deleteTarget) return;
		await deleteRole(deleteTarget.id);
		setDeleteTarget(null);
	};

	const togglePermission = (value: string, checked: boolean, field: { value: string[] }) => {
		if (checked) {
			return Array.from(new Set([...field.value, value]));
		}
		return field.value.filter((permission) => permission !== value);
	};

	return (
		<div className="space-y-6 min-w-0">
			<div className="flex items-center justify-between gap-3">
				<div>
					<h3 className="text-sm font-semibold tracking-tight">Platform roles</h3>
					<p className="text-xs text-muted-foreground">
						Roles grant platform-admin permissions to specific users. System roles cannot be edited
						or deleted.
					</p>
				</div>
				<Button size="sm" onClick={openCreateDialog}>
					Create role
				</Button>
			</div>

			{isLoading ? (
				<div className="space-y-2">
					{["skeleton-a", "skeleton-b", "skeleton-c"].map((key) => (
						<Skeleton key={key} className="h-12 w-full" />
					))}
				</div>
			) : sortedRoles.length > 0 ? (
				<div className="rounded-md border">
					<Table>
						<TableHeader>
							<TableRow>
								<TableHead>Name</TableHead>
								<TableHead>Description</TableHead>
								<TableHead>Permissions</TableHead>
								<TableHead>Type</TableHead>
								<TableHead className="text-right">Actions</TableHead>
							</TableRow>
						</TableHeader>
						<TableBody>
							{sortedRoles.map((role) => (
								<TableRow key={role.id}>
									<TableCell className="font-medium">{role.name}</TableCell>
									<TableCell className="max-w-[320px] truncate text-muted-foreground">
										{role.description || "—"}
									</TableCell>
									<TableCell>
										{role.permissions.includes("*")
											? "All permissions"
											: `${role.permissions.length} permission${role.permissions.length === 1 ? "" : "s"}`}
									</TableCell>
									<TableCell>
										{role.is_system_role ? (
											<Badge variant="secondary">System</Badge>
										) : (
											<Badge variant="outline">Custom</Badge>
										)}
									</TableCell>
									<TableCell className="text-right">
										<div className="flex justify-end gap-1">
											<Button
												variant="ghost"
												size="icon"
												className="h-8 w-8"
												disabled={role.is_system_role}
												onClick={() => openEditDialog(role)}
											>
												<Pencil className="h-4 w-4" />
											</Button>
											<Button
												variant="ghost"
												size="icon"
												className="h-8 w-8 text-muted-foreground hover:text-destructive"
												disabled={role.is_system_role}
												onClick={() => setDeleteTarget(role)}
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
				<p className="py-6 text-center text-sm text-muted-foreground">No roles yet.</p>
			)}

			<Dialog open={formOpen} onOpenChange={setFormOpen}>
				<DialogContent className="max-w-lg">
					<DialogHeader>
						<DialogTitle>{editingRole ? "Edit role" : "Create role"}</DialogTitle>
						<DialogDescription>
							{editingRole
								? "Update the role's name, description, and permissions."
								: "Define a name and the set of platform permissions this role grants."}
						</DialogDescription>
					</DialogHeader>

					<Form {...form}>
						<form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
							<FormField
								control={form.control}
								name="name"
								render={({ field }) => (
									<FormItem>
										<FormLabel>Name</FormLabel>
										<FormControl>
											<Input placeholder="Billing Admin" disabled={isMutating} {...field} />
										</FormControl>
										<FormMessage />
									</FormItem>
								)}
							/>

							<FormField
								control={form.control}
								name="description"
								render={({ field }) => (
									<FormItem>
										<FormLabel>
											Description{" "}
											<span className="text-muted-foreground font-normal">(optional)</span>
										</FormLabel>
										<FormControl>
											<Textarea
												placeholder="What can this role do?"
												disabled={isMutating}
												rows={2}
												{...field}
											/>
										</FormControl>
										<FormMessage />
									</FormItem>
								)}
							/>

							<FormField
								control={form.control}
								name="permissions"
								render={({ field }) => (
									<FormItem>
										<FormLabel>Permissions</FormLabel>
										<FormControl>
											<ScrollArea className="h-56 rounded-md border p-3">
												<div className="space-y-2">
													{permissions.map((permission) => (
														<div key={permission.value} className="flex items-start gap-2">
															<Checkbox
																id={`permission-${permission.value}`}
																checked={field.value.includes(permission.value)}
																disabled={isMutating}
																onCheckedChange={(checked) =>
																	field.onChange(
																		togglePermission(permission.value, !!checked, field)
																	)
																}
															/>
															<Label
																htmlFor={`permission-${permission.value}`}
																className="flex flex-col gap-0.5 font-normal"
															>
																<span className="text-sm">{permission.name}</span>
																<span className="text-xs text-muted-foreground">
																	{permission.description}
																</span>
															</Label>
														</div>
													))}
													{permissions.length === 0 && (
														<p className="text-xs text-muted-foreground">
															No permissions available.
														</p>
													)}
												</div>
											</ScrollArea>
										</FormControl>
										<FormMessage />
									</FormItem>
								)}
							/>

							<DialogFooter>
								<Button
									type="button"
									variant="secondary"
									size="sm"
									disabled={isMutating}
									onClick={() => setFormOpen(false)}
								>
									Cancel
								</Button>
								<Button
									type="submit"
									size="sm"
									disabled={isMutating}
									className="relative min-w-[100px]"
								>
									<span className={isMutating ? "opacity-0" : ""}>
										{editingRole ? "Save changes" : "Create role"}
									</span>
									{isMutating && <Spinner size="sm" className="absolute" />}
								</Button>
							</DialogFooter>
						</form>
					</Form>
				</DialogContent>
			</Dialog>

			<AlertDialog
				open={deleteTarget !== null}
				onOpenChange={(open) => !open && setDeleteTarget(null)}
			>
				<AlertDialogContent>
					<AlertDialogHeader>
						<AlertDialogTitle className="flex items-center gap-2">
							<ShieldAlert className="h-4 w-4 text-destructive" />
							Delete role?
						</AlertDialogTitle>
						<AlertDialogDescription>
							<span className="font-medium text-foreground">{deleteTarget?.name}</span> will be
							permanently removed, along with any assignments to it. This cannot be undone.
						</AlertDialogDescription>
					</AlertDialogHeader>
					<AlertDialogFooter>
						<AlertDialogCancel disabled={isMutating}>Cancel</AlertDialogCancel>
						<AlertDialogAction
							disabled={isMutating}
							className="bg-destructive text-white hover:bg-destructive/90"
							onClick={(event) => {
								event.preventDefault();
								void handleConfirmDelete();
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
		</div>
	);
}
