"use client";

import { useFormContext } from "react-hook-form";
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { ModelFormValues } from "./model-form-schema";

/** Prompt behavior section: system instructions and citation handling. */
export function ModelPromptFields({ isMutating }: { isMutating: boolean }) {
	const { control } = useFormContext<ModelFormValues>();

	return (
		<div className="space-y-4">
			<FormField
				control={control}
				name="use_default_system_instructions"
				render={({ field }) => (
					<FormItem className="flex flex-row items-center justify-between rounded-md border p-3">
						<div className="space-y-0.5">
							<FormLabel>Use default system instructions</FormLabel>
							<p className="text-xs text-muted-foreground">
								Turn off to override with the custom instructions below.
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

			<FormField
				control={control}
				name="system_instructions"
				render={({ field }) => (
					<FormItem>
						<FormLabel>
							Custom system instructions{" "}
							<span className="text-muted-foreground font-normal">(optional)</span>
						</FormLabel>
						<FormControl>
							<Textarea rows={4} disabled={isMutating} {...field} />
						</FormControl>
						<FormMessage />
					</FormItem>
				)}
			/>

			<FormField
				control={control}
				name="citations_enabled"
				render={({ field }) => (
					<FormItem className="flex flex-row items-center justify-between rounded-md border p-3">
						<FormLabel>Citations enabled</FormLabel>
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
		</div>
	);
}
