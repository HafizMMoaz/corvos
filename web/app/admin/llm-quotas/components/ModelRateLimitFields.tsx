"use client";

import { useFormContext } from "react-hook-form";
import { FormControl, FormField, FormItem, FormLabel, FormMessage } from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import type { ModelFormValues } from "./model-form-schema";

/** Rate limits & routing section: throughput caps, free-tier reservation, and router placement. */
export function ModelRateLimitFields({ isMutating }: { isMutating: boolean }) {
	const { control } = useFormContext<ModelFormValues>();

	return (
		<div className="space-y-4">
			<div className="grid grid-cols-2 gap-3">
				<FormField
					control={control}
					name="rpm"
					render={({ field }) => (
						<FormItem>
							<FormLabel>
								RPM <span className="text-muted-foreground font-normal">(optional)</span>
							</FormLabel>
							<FormControl>
								<Input
									inputMode="numeric"
									placeholder="Unlimited"
									disabled={isMutating}
									{...field}
								/>
							</FormControl>
							<FormMessage />
						</FormItem>
					)}
				/>
				<FormField
					control={control}
					name="tpm"
					render={({ field }) => (
						<FormItem>
							<FormLabel>
								TPM <span className="text-muted-foreground font-normal">(optional)</span>
							</FormLabel>
							<FormControl>
								<Input
									inputMode="numeric"
									placeholder="Unlimited"
									disabled={isMutating}
									{...field}
								/>
							</FormControl>
							<FormMessage />
						</FormItem>
					)}
				/>
			</div>

			<FormField
				control={control}
				name="quota_reserve_tokens"
				render={({ field }) => (
					<FormItem>
						<FormLabel>
							Quota reserve tokens{" "}
							<span className="text-muted-foreground font-normal">(optional)</span>
						</FormLabel>
						<FormControl>
							<Input inputMode="numeric" placeholder="Default" disabled={isMutating} {...field} />
						</FormControl>
						<FormMessage />
					</FormItem>
				)}
			/>

			<FormField
				control={control}
				name="router_pool_eligible"
				render={({ field }) => (
					<FormItem className="flex flex-row items-center justify-between rounded-md border p-3">
						<div className="space-y-0.5">
							<FormLabel>Router pool eligible</FormLabel>
							<p className="text-xs text-muted-foreground">
								Eligible for automatic model selection by the router.
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
				name="is_planner"
				render={({ field }) => (
					<FormItem className="flex flex-row items-center justify-between rounded-md border p-3">
						<div className="space-y-0.5">
							<FormLabel>Planner model</FormLabel>
							<p className="text-xs text-muted-foreground">
								Used for planning/orchestration steps rather than direct chat.
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
		</div>
	);
}
