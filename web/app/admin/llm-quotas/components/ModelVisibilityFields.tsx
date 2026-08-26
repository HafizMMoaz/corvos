"use client";

import { useFormContext } from "react-hook-form";
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { ModelFormValues } from "./model-form-schema";

function SwitchRow({
	name,
	label,
	description,
	isMutating,
}: {
	name: "anonymous_enabled" | "seo_enabled" | "is_enabled";
	label: string;
	description: string;
	isMutating: boolean;
}) {
	const { control } = useFormContext<ModelFormValues>();
	return (
		<FormField
			control={control}
			name={name}
			render={({ field }) => (
				<FormItem className="flex flex-row items-center justify-between rounded-md border p-3">
					<div className="space-y-0.5">
						<FormLabel>{label}</FormLabel>
						<p className="text-xs text-muted-foreground">{description}</p>
					</div>
					<FormControl>
						<Switch checked={field.value} onCheckedChange={field.onChange} disabled={isMutating} />
					</FormControl>
				</FormItem>
			)}
		/>
	);
}

/** Visibility section: anonymous/public access, SEO listing, and the enabled switch. */
export function ModelVisibilityFields({ isMutating }: { isMutating: boolean }) {
	const { control } = useFormContext<ModelFormValues>();

	return (
		<div className="space-y-4">
			<SwitchRow
				name="is_enabled"
				label="Enabled"
				description="Disabled models are excluded from the live catalog."
				isMutating={isMutating}
			/>
			<SwitchRow
				name="anonymous_enabled"
				label="Anonymous access"
				description="Allow signed-out visitors to use this model."
				isMutating={isMutating}
			/>
			<SwitchRow
				name="seo_enabled"
				label="SEO listing"
				description="List this model on its own public, indexable page."
				isMutating={isMutating}
			/>

			<FormField
				control={control}
				name="seo_slug"
				render={({ field }) => (
					<FormItem>
						<FormLabel>
							SEO slug <span className="text-muted-foreground font-normal">(optional)</span>
						</FormLabel>
						<FormControl>
							<Input placeholder="gpt-4o" disabled={isMutating} {...field} />
						</FormControl>
						<FormMessage />
					</FormItem>
				)}
			/>
			<FormField
				control={control}
				name="seo_title"
				render={({ field }) => (
					<FormItem>
						<FormLabel>
							SEO title <span className="text-muted-foreground font-normal">(optional)</span>
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
				name="seo_description"
				render={({ field }) => (
					<FormItem>
						<FormLabel>
							SEO description <span className="text-muted-foreground font-normal">(optional)</span>
						</FormLabel>
						<FormControl>
							<Textarea rows={2} disabled={isMutating} {...field} />
						</FormControl>
						<FormMessage />
					</FormItem>
				)}
			/>
		</div>
	);
}
