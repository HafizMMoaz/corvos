"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import * as z from "zod";
import { Button } from "@/components/ui/button";
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
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type {
	AdminLlmProviderCreateRequest,
	AdminLlmProviderRead,
	AdminLlmProviderUpdateRequest,
} from "@/contracts/types/admin-llm.types";
import { EnumOrCustomField } from "./EnumOrCustomField";
import { ProviderApiKeyField } from "./ProviderApiKeyField";

// Known `Transport`/`AuthStyle` value sets from
// backend/app/services/provider_registry.py -- offered as select options, but
// the backend stores both as plain strings with no server-side enum
// constraint, so a custom value is also accepted (see EnumOrCustomField).
const TRANSPORT_OPTIONS = ["native", "openai_compatible", "ollama"] as const;
const AUTH_STYLE_OPTIONS = ["bearer", "x-api-key", "none", "native"] as const;

const providerFormSchema = z.object({
	provider_key: z.string().min(1, "Provider key is required"),
	display_name: z.string().min(1, "Display name is required"),
	transport: z.string().min(1, "Transport is required"),
	litellm_prefix: z.string(),
	default_base_url: z.string(),
	base_url_required: z.boolean(),
	auth_style: z.string().min(1, "Auth style is required"),
	api_key: z.string(),
	clear_api_key: z.boolean(),
	api_base_override: z.string(),
	notes: z.string(),
	is_enabled: z.boolean(),
});

export type ProviderFormValues = z.infer<typeof providerFormSchema>;

const EMPTY_VALUES: ProviderFormValues = {
	provider_key: "",
	display_name: "",
	transport: "native",
	litellm_prefix: "",
	default_base_url: "",
	base_url_required: false,
	auth_style: "bearer",
	api_key: "",
	clear_api_key: false,
	api_base_override: "",
	notes: "",
	is_enabled: true,
};

/** `""` -> `null` for optional text fields; the backend stores absence as null, not empty string. */
function blankToNull(value: string): string | null {
	const trimmed = value.trim();
	return trimmed ? trimmed : null;
}

interface ProviderFormDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	/** Provider being edited, or null when the dialog is in create mode. */
	provider: AdminLlmProviderRead | null;
	isMutating: boolean;
	onCreate: (body: AdminLlmProviderCreateRequest) => Promise<void>;
	onUpdate: (id: number, body: AdminLlmProviderUpdateRequest) => Promise<void>;
}

export function ProviderFormDialog({
	open,
	onOpenChange,
	provider,
	isMutating,
	onCreate,
	onUpdate,
}: ProviderFormDialogProps) {
	const isEditing = provider !== null;

	const form = useForm<ProviderFormValues>({
		resolver: zodResolver(providerFormSchema),
		defaultValues: EMPTY_VALUES,
	});

	useEffect(() => {
		if (!open) return;
		if (provider) {
			form.reset({
				provider_key: provider.provider_key,
				display_name: provider.display_name,
				transport: provider.transport,
				litellm_prefix: provider.litellm_prefix ?? "",
				default_base_url: provider.default_base_url ?? "",
				base_url_required: provider.base_url_required,
				auth_style: provider.auth_style,
				api_key: "",
				clear_api_key: false,
				api_base_override: provider.api_base_override ?? "",
				notes: provider.notes ?? "",
				is_enabled: provider.is_enabled,
			});
		} else {
			form.reset(EMPTY_VALUES);
		}
	}, [open, provider, form.reset]);

	async function handleSubmit(values: ProviderFormValues) {
		const shared = {
			provider_key: values.provider_key,
			display_name: values.display_name,
			transport: values.transport,
			litellm_prefix: blankToNull(values.litellm_prefix),
			default_base_url: blankToNull(values.default_base_url),
			base_url_required: values.base_url_required,
			auth_style: values.auth_style,
			api_base_override: blankToNull(values.api_base_override),
			notes: blankToNull(values.notes),
		};

		try {
			if (isEditing && provider) {
				const payload: AdminLlmProviderUpdateRequest = { ...shared, is_enabled: values.is_enabled };
				if (values.clear_api_key) {
					payload.api_key = null;
				} else if (values.api_key.trim()) {
					payload.api_key = values.api_key.trim();
				}
				await onUpdate(provider.id, payload);
			} else {
				const payload: AdminLlmProviderCreateRequest = { ...shared };
				if (values.api_key.trim()) {
					payload.api_key = values.api_key.trim();
				}
				await onCreate(payload);
			}
			onOpenChange(false);
		} catch {
			// hook already surfaced a toast; keep the dialog open to retry
		}
	}

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-h-[85vh] max-w-lg overflow-y-auto">
				<DialogHeader>
					<DialogTitle>{isEditing ? "Edit provider" : "Add provider"}</DialogTitle>
					<DialogDescription>
						{isEditing
							? "Update this provider's connection details."
							: "Connect a new upstream LLM provider. It's created enabled by default."}
					</DialogDescription>
				</DialogHeader>

				<Form {...form}>
					<form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
						<div className="grid grid-cols-2 gap-3">
							<FormField
								control={form.control}
								name="provider_key"
								render={({ field }) => (
									<FormItem>
										<FormLabel>Provider key</FormLabel>
										<FormControl>
											<Input placeholder="openai" disabled={isMutating} {...field} />
										</FormControl>
										<FormMessage />
									</FormItem>
								)}
							/>
							<FormField
								control={form.control}
								name="display_name"
								render={({ field }) => (
									<FormItem>
										<FormLabel>Display name</FormLabel>
										<FormControl>
											<Input placeholder="OpenAI" disabled={isMutating} {...field} />
										</FormControl>
										<FormMessage />
									</FormItem>
								)}
							/>
						</div>

						<div className="grid grid-cols-2 gap-3">
							<FormField
								control={form.control}
								name="transport"
								render={({ field }) => (
									<FormItem>
										<FormLabel>Transport</FormLabel>
										<FormControl>
											<EnumOrCustomField
												id="provider-transport"
												options={TRANSPORT_OPTIONS}
												value={field.value}
												onChange={field.onChange}
												disabled={isMutating}
												placeholder="Select transport"
											/>
										</FormControl>
										<FormMessage />
									</FormItem>
								)}
							/>
							<FormField
								control={form.control}
								name="auth_style"
								render={({ field }) => (
									<FormItem>
										<FormLabel>Auth style</FormLabel>
										<FormControl>
											<EnumOrCustomField
												id="provider-auth-style"
												options={AUTH_STYLE_OPTIONS}
												value={field.value}
												onChange={field.onChange}
												disabled={isMutating}
												placeholder="Select auth style"
											/>
										</FormControl>
										<FormMessage />
									</FormItem>
								)}
							/>
						</div>

						<FormField
							control={form.control}
							name="litellm_prefix"
							render={({ field }) => (
								<FormItem>
									<FormLabel>
										LiteLLM prefix{" "}
										<span className="text-muted-foreground font-normal">(optional)</span>
									</FormLabel>
									<FormControl>
										<Input placeholder="openai" disabled={isMutating} {...field} />
									</FormControl>
									<FormMessage />
								</FormItem>
							)}
						/>

						<div className="grid grid-cols-2 gap-3">
							<FormField
								control={form.control}
								name="default_base_url"
								render={({ field }) => (
									<FormItem>
										<FormLabel>
											Default base URL{" "}
											<span className="text-muted-foreground font-normal">(optional)</span>
										</FormLabel>
										<FormControl>
											<Input
												placeholder="https://api.openai.com/v1"
												disabled={isMutating}
												{...field}
											/>
										</FormControl>
										<FormMessage />
									</FormItem>
								)}
							/>
							<FormField
								control={form.control}
								name="api_base_override"
								render={({ field }) => (
									<FormItem>
										<FormLabel>
											Base URL override{" "}
											<span className="text-muted-foreground font-normal">(optional)</span>
										</FormLabel>
										<FormControl>
											<Input placeholder="" disabled={isMutating} {...field} />
										</FormControl>
										<FormMessage />
									</FormItem>
								)}
							/>
						</div>

						<FormField
							control={form.control}
							name="base_url_required"
							render={({ field }) => (
								<FormItem className="flex flex-row items-center justify-between rounded-md border p-3">
									<div className="space-y-0.5">
										<FormLabel>Base URL required</FormLabel>
										<p className="text-xs text-muted-foreground">
											Models under this provider must supply a base URL.
										</p>
									</div>
									<FormControl>
										<Switch
											checked={field.value}
											onCheckedChange={field.onChange}
											disabled={isMutating}
										/>
									</FormControl>
								</FormItem>
							)}
						/>

						{isEditing && (
							<FormField
								control={form.control}
								name="is_enabled"
								render={({ field }) => (
									<FormItem className="flex flex-row items-center justify-between rounded-md border p-3">
										<div className="space-y-0.5">
											<FormLabel>Enabled</FormLabel>
											<p className="text-xs text-muted-foreground">
												Disabled providers are excluded from the live catalog.
											</p>
										</div>
										<FormControl>
											<Switch
												checked={field.value}
												onCheckedChange={field.onChange}
												disabled={isMutating}
											/>
										</FormControl>
									</FormItem>
								)}
							/>
						)}

						<ProviderApiKeyField
							isMutating={isMutating}
							isEditing={isEditing}
							hasExistingKey={provider?.has_api_key ?? false}
						/>

						<FormField
							control={form.control}
							name="notes"
							render={({ field }) => (
								<FormItem>
									<FormLabel>
										Notes <span className="text-muted-foreground font-normal">(optional)</span>
									</FormLabel>
									<FormControl>
										<Textarea rows={2} disabled={isMutating} {...field} />
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
								onClick={() => onOpenChange(false)}
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
									{isEditing ? "Save changes" : "Add provider"}
								</span>
								{isMutating && <Spinner size="sm" className="absolute" />}
							</Button>
						</DialogFooter>
					</form>
				</Form>
			</DialogContent>
		</Dialog>
	);
}
