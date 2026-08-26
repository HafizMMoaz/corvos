"use client";

import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import { useFormContext } from "react-hook-form";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { ProviderFormValues } from "./ProviderFormDialog";

/**
 * The API key subsection of the provider form: a masked input with its own
 * show/hide toggle (mirrors SettingEditDialog's secret input), plus -- only
 * when editing a provider that already has a key stored -- a checkbox to
 * clear it outright. Split out of ProviderFormDialog to keep that file from
 * growing into a single oversized component.
 */
export function ProviderApiKeyField({
	isMutating,
	isEditing,
	hasExistingKey,
}: {
	isMutating: boolean;
	isEditing: boolean;
	hasExistingKey: boolean;
}) {
	const { control, watch } = useFormContext<ProviderFormValues>();
	const [showApiKey, setShowApiKey] = useState(false);
	const clearApiKey = watch("clear_api_key");

	return (
		<>
			<FormField
				control={control}
				name="api_key"
				render={({ field }) => (
					<FormItem>
						<FormLabel>
							{isEditing ? "New API key" : "API key"}{" "}
							<span className="text-muted-foreground font-normal">
								({isEditing ? "leave blank to keep the current key" : "optional"})
							</span>
						</FormLabel>
						<FormControl>
							<div className="relative">
								<Input
									value={field.value}
									onChange={field.onChange}
									placeholder={isEditing ? "Unchanged" : "Enter an API key"}
									type={showApiKey ? "text" : "password"}
									className="pr-11"
									disabled={isMutating || clearApiKey}
								/>
								<Button
									type="button"
									variant="ghost"
									size="icon"
									className="absolute top-1/2 right-1 size-8 -translate-y-1/2 text-muted-foreground"
									onClick={() => setShowApiKey((current) => !current)}
									disabled={!field.value}
									aria-label={showApiKey ? "Hide value" : "Show value"}
								>
									{showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
								</Button>
							</div>
						</FormControl>
						<FormMessage />
					</FormItem>
				)}
			/>

			{isEditing && hasExistingKey && (
				<FormField
					control={control}
					name="clear_api_key"
					render={({ field }) => (
						<FormItem className="flex flex-row items-center gap-2">
							<FormControl>
								<Checkbox
									id="provider-clear-api-key"
									checked={field.value}
									onCheckedChange={(checked) => field.onChange(!!checked)}
									disabled={isMutating}
								/>
							</FormControl>
							<Label htmlFor="provider-clear-api-key" className="font-normal">
								Clear the stored API key
							</Label>
						</FormItem>
					)}
				/>
			)}
		</>
	);
}
