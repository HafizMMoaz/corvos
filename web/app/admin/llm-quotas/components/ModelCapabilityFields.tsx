"use client";

import { useFormContext } from "react-hook-form";
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import type { ModelFormValues } from "./model-form-schema";

/** Capabilities section: what this model can accept/do. */
export function ModelCapabilityFields({ isMutating }: { isMutating: boolean }) {
	const { control } = useFormContext<ModelFormValues>();

	return (
		<div className="space-y-4">
			<FormField
				control={control}
				name="supports_image_input"
				render={({ field }) => (
					<FormItem className="flex flex-row items-center justify-between rounded-md border p-3">
						<FormLabel>Supports image input</FormLabel>
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
			<FormField
				control={control}
				name="supports_tools"
				render={({ field }) => (
					<FormItem className="flex flex-row items-center justify-between rounded-md border p-3">
						<FormLabel>Supports tools</FormLabel>
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
			<FormField
				control={control}
				name="max_input_tokens"
				render={({ field }) => (
					<FormItem>
						<FormLabel>
							Max input tokens <span className="text-muted-foreground font-normal">(optional)</span>
						</FormLabel>
						<FormControl>
							<Input inputMode="numeric" placeholder="Unlimited" disabled={isMutating} {...field} />
						</FormControl>
						<FormMessage />
					</FormItem>
				)}
			/>
		</div>
	);
}
