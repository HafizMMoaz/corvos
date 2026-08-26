"use client";

import { useFormContext } from "react-hook-form";
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { ModelFormValues } from "./model-form-schema";

/**
 * Provider overrides section: per-model connection overrides plus
 * `litellm_params`, an arbitrary JSON object passed through to litellm. No
 * rich JSON editor exists yet in this codebase, so this is a plain textarea
 * validated with JSON.parse (see `optionalJsonObjectField` in
 * model-form-schema.ts) -- consistent with the brief's guidance that this is
 * sufficient until a JSON-typed field actually needs richer editing.
 */
export function ModelProviderOverrideFields({ isMutating }: { isMutating: boolean }) {
	const { control } = useFormContext<ModelFormValues>();

	return (
		<div className="space-y-4">
			<div className="grid grid-cols-2 gap-3">
				<FormField
					control={control}
					name="api_base_override"
					render={({ field }) => (
						<FormItem>
							<FormLabel>
								Base URL override{" "}
								<span className="text-muted-foreground font-normal">(optional)</span>
							</FormLabel>
							<FormControl>
								<Input disabled={isMutating} {...field} />
							</FormControl>
							<FormMessage />
						</FormItem>
					)}
				/>
				<FormField
					control={control}
					name="api_version"
					render={({ field }) => (
						<FormItem>
							<FormLabel>
								API version <span className="text-muted-foreground font-normal">(optional)</span>
							</FormLabel>
							<FormControl>
								<Input disabled={isMutating} {...field} />
							</FormControl>
							<FormMessage />
						</FormItem>
					)}
				/>
			</div>

			<FormField
				control={control}
				name="litellm_params"
				render={({ field }) => (
					<FormItem>
						<FormLabel>
							LiteLLM params (JSON){" "}
							<span className="text-muted-foreground font-normal">(optional)</span>
						</FormLabel>
						<FormControl>
							<Textarea
								rows={4}
								placeholder={'{\n  "temperature": 0.7\n}'}
								className="font-mono text-xs"
								disabled={isMutating}
								{...field}
							/>
						</FormControl>
						<FormMessage />
					</FormItem>
				)}
			/>
		</div>
	);
}
