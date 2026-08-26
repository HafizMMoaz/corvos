"use client";

import { useFormContext } from "react-hook-form";
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import type {
	AdminLlmDiscoveredModelRead,
	AdminLlmProviderRead,
} from "@/contracts/types/admin-llm.types";
import { EnumOrCustomField } from "./EnumOrCustomField";
import type { ModelFormValues } from "./model-form-schema";

/** Identity section: which provider this model belongs to, its identifiers, and its billing tier. */
export function ModelIdentityFields({
	providers,
	isMutating,
	discoveredModels,
	isDiscovering,
	discoveryError,
}: {
	providers: AdminLlmProviderRead[];
	isMutating: boolean;
	/** Live model list for the currently selected provider (Track 4). Empty when nothing has been discovered yet. */
	discoveredModels: AdminLlmDiscoveredModelRead[];
	isDiscovering: boolean;
	/** Discovery failure message, if the last attempt failed. Never blocks manual entry. */
	discoveryError: string | null;
}) {
	const { control, getValues, setValue } = useFormContext<ModelFormValues>();
	const providerSelected = getValues("provider_id") !== "";
	const modelOptions = discoveredModels.map((discovered) => discovered.model_id);

	/**
	 * When the admin picks a discovered model from the dropdown, pre-fill the
	 * display name and capability checkboxes from that entry -- but only for
	 * fields still at their untouched defaults, so a hand-edited value is
	 * never clobbered. Free-text entry (a value not in `discoveredModels`)
	 * skips this entirely.
	 */
	function applyDiscoveredDefaults(modelId: string) {
		const match = discoveredModels.find((discovered) => discovered.model_id === modelId);
		if (!match) return;
		if (!getValues("name").trim()) {
			setValue("name", match.display_name || match.model_id, { shouldDirty: true });
		}
		if (!getValues("supports_image_input") && match.supports_image_input) {
			setValue("supports_image_input", true, { shouldDirty: true });
		}
		if (!getValues("supports_tools") && match.supports_tools) {
			setValue("supports_tools", true, { shouldDirty: true });
		}
	}

	return (
		<div className="space-y-4">
			<FormField
				control={control}
				name="provider_id"
				render={({ field }) => (
					<FormItem>
						<FormLabel>Provider</FormLabel>
						<Select value={field.value} onValueChange={field.onChange} disabled={isMutating}>
							<FormControl>
								<SelectTrigger className="w-full">
									<SelectValue placeholder="Select a provider" />
								</SelectTrigger>
							</FormControl>
							<SelectContent>
								{providers.map((provider) => (
									<SelectItem key={provider.id} value={String(provider.id)}>
										{provider.display_name}
									</SelectItem>
								))}
							</SelectContent>
						</Select>
						<FormMessage />
					</FormItem>
				)}
			/>

			<div className="grid grid-cols-2 gap-3">
				<FormField
					control={control}
					name="name"
					render={({ field }) => (
						<FormItem>
							<FormLabel>Name</FormLabel>
							<FormControl>
								<Input placeholder="GPT-4o" disabled={isMutating} {...field} />
							</FormControl>
							<FormMessage />
						</FormItem>
					)}
				/>
				<FormField
					control={control}
					name="model_name"
					render={({ field }) => (
						<FormItem>
							<FormLabel>Model name</FormLabel>
							<FormControl>
								<EnumOrCustomField
									id="model-model-name"
									options={modelOptions}
									value={field.value}
									onChange={(next) => {
										field.onChange(next);
										applyDiscoveredDefaults(next);
									}}
									disabled={isMutating}
									placeholder="Select a discovered model"
								/>
							</FormControl>
							{isDiscovering && (
								<p className="text-muted-foreground text-xs">Loading available models...</p>
							)}
							{!isDiscovering && discoveryError && (
								<p className="text-muted-foreground text-xs">
									Could not fetch live models ({discoveryError}). Enter a model name manually.
								</p>
							)}
							{!isDiscovering &&
								!discoveryError &&
								providerSelected &&
								modelOptions.length === 0 && (
									<p className="text-muted-foreground text-xs">
										No models discovered for this provider. Enter a model name manually.
									</p>
								)}
							<FormMessage />
						</FormItem>
					)}
				/>
			</div>

			<FormField
				control={control}
				name="billing_tier"
				render={({ field }) => (
					<FormItem>
						<FormLabel>Billing tier</FormLabel>
						<Select value={field.value} onValueChange={field.onChange} disabled={isMutating}>
							<FormControl>
								<SelectTrigger className="w-full">
									<SelectValue />
								</SelectTrigger>
							</FormControl>
							<SelectContent>
								<SelectItem value="premium">Premium</SelectItem>
								<SelectItem value="free">Free</SelectItem>
							</SelectContent>
						</Select>
						<FormMessage />
					</FormItem>
				)}
			/>
		</div>
	);
}
