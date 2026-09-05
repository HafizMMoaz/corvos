"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type {
	PlanCreateRequest,
	PlanRead,
	PlanUpdateRequest,
} from "@/contracts/types/admin-billing.types";

interface PlanFormDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	/** Plan being edited, or null when the dialog is in create mode. */
	plan: PlanRead | null;
	isMutating: boolean;
	onCreate: (body: PlanCreateRequest) => Promise<void>;
	onUpdate: (id: number, body: PlanUpdateRequest) => Promise<void>;
}

interface PlanDraft {
	planKey: string;
	name: string;
	description: string;
	monthlyCreditMicros: string;
	paddlePriceId: string;
	isActive: boolean;
}

const EMPTY_DRAFT: PlanDraft = {
	planKey: "",
	name: "",
	description: "",
	monthlyCreditMicros: "0",
	paddlePriceId: "",
	isActive: true,
};

function planToDraft(plan: PlanRead): PlanDraft {
	return {
		planKey: plan.plan_key,
		name: plan.name,
		description: plan.description ?? "",
		monthlyCreditMicros: String(plan.monthly_credit_micros),
		paddlePriceId: plan.paddle_price_id ?? "",
		isActive: plan.is_active,
	};
}

/**
 * Create/edit dialog for a plan. Small enough for plain controlled inputs
 * (SettingEditDialog's shape) rather than the react-hook-form setup the big
 * model dialog needs. `paddle_price_id` is edit-only: the backend rules it
 * out on create (assign it once the matching Paddle price exists).
 */
export function PlanFormDialog({
	open,
	onOpenChange,
	plan,
	isMutating,
	onCreate,
	onUpdate,
}: PlanFormDialogProps) {
	const isEditing = plan !== null;
	const [draft, setDraft] = useState<PlanDraft>(EMPTY_DRAFT);

	useEffect(() => {
		if (!open) return;
		setDraft(plan ? planToDraft(plan) : EMPTY_DRAFT);
	}, [open, plan]);

	const monthlyCreditMicros = Number(draft.monthlyCreditMicros);
	const creditMicrosValid =
		draft.monthlyCreditMicros.trim() !== "" &&
		Number.isInteger(monthlyCreditMicros) &&
		monthlyCreditMicros >= 0;
	const valid = draft.planKey.trim() !== "" && draft.name.trim() !== "" && creditMicrosValid;

	async function handleSubmit() {
		if (!valid) return;
		try {
			if (isEditing && plan) {
				await onUpdate(plan.id, {
					plan_key: draft.planKey.trim(),
					name: draft.name.trim(),
					description: draft.description.trim() === "" ? null : draft.description.trim(),
					monthly_credit_micros: monthlyCreditMicros,
					paddle_price_id: draft.paddlePriceId.trim() === "" ? null : draft.paddlePriceId.trim(),
					is_active: draft.isActive,
				});
			} else {
				await onCreate({
					plan_key: draft.planKey.trim(),
					name: draft.name.trim(),
					description: draft.description.trim() === "" ? null : draft.description.trim(),
					monthly_credit_micros: monthlyCreditMicros,
					is_active: draft.isActive,
				});
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
					<DialogTitle>{isEditing ? "Edit plan" : "Add plan"}</DialogTitle>
					<DialogDescription>
						{isEditing
							? "Update this plan's configuration."
							: "Create a plan users can subscribe to or be assigned."}
					</DialogDescription>
				</DialogHeader>

				<div className="space-y-4">
					<div className="space-y-2">
						<Label htmlFor="plan-key">Plan key</Label>
						<Input
							id="plan-key"
							value={draft.planKey}
							onChange={(event) => setDraft({ ...draft, planKey: event.target.value })}
							placeholder="pro"
							className="font-mono"
							disabled={isMutating}
						/>
						<p className="text-xs text-muted-foreground">
							Stable machine identifier (unique across plans).
						</p>
					</div>

					<div className="space-y-2">
						<Label htmlFor="plan-name">Name</Label>
						<Input
							id="plan-name"
							value={draft.name}
							onChange={(event) => setDraft({ ...draft, name: event.target.value })}
							placeholder="Pro"
							disabled={isMutating}
						/>
					</div>

					<div className="space-y-2">
						<Label htmlFor="plan-description">Description</Label>
						<Textarea
							id="plan-description"
							value={draft.description}
							onChange={(event) => setDraft({ ...draft, description: event.target.value })}
							placeholder="What this plan includes"
							rows={2}
							disabled={isMutating}
						/>
					</div>

					<div className="space-y-2">
						<Label htmlFor="plan-credits">Monthly credit grant (micros)</Label>
						<Input
							id="plan-credits"
							value={draft.monthlyCreditMicros}
							onChange={(event) => setDraft({ ...draft, monthlyCreditMicros: event.target.value })}
							type="number"
							min={0}
							step={1_000_000}
							disabled={isMutating}
							aria-invalid={!creditMicrosValid}
						/>
						<p className="text-xs text-muted-foreground">
							1,000,000 micros = $1.00.
							{creditMicrosValid
								? ` Currently ${(monthlyCreditMicros / 1_000_000).toLocaleString(undefined, { maximumFractionDigits: 2 })} USD/month.`
								: ""}
						</p>
					</div>

					{isEditing && (
						<div className="space-y-2">
							<Label htmlFor="plan-paddle-price">Paddle price ID</Label>
							<Input
								id="plan-paddle-price"
								value={draft.paddlePriceId}
								onChange={(event) => setDraft({ ...draft, paddlePriceId: event.target.value })}
								placeholder="pri_..."
								className="font-mono"
								disabled={isMutating}
							/>
							<p className="text-xs text-muted-foreground">
								Links this plan to its Paddle Billing price. Leave empty for admin-assigned only
								plans. Each price can belong to at most one plan.
							</p>
						</div>
					)}

					<div className="flex items-center justify-between rounded-md border px-3 py-2.5">
						<div className="space-y-0.5">
							<Label htmlFor="plan-active">Active</Label>
							<p className="text-xs text-muted-foreground">
								Inactive plans stay assignable but read as retired.
							</p>
						</div>
						<Switch
							id="plan-active"
							checked={draft.isActive}
							onCheckedChange={(checked) => setDraft({ ...draft, isActive: checked })}
							disabled={isMutating}
						/>
					</div>
				</div>

				<DialogFooter>
					<Button
						type="button"
						variant="secondary"
						size="sm"
						onClick={() => onOpenChange(false)}
						disabled={isMutating}
					>
						Cancel
					</Button>
					<Button
						type="button"
						size="sm"
						disabled={isMutating || !valid}
						onClick={() => void handleSubmit()}
						className="relative min-w-[100px]"
					>
						<span className={isMutating ? "opacity-0" : ""}>
							{isEditing ? "Save changes" : "Add plan"}
						</span>
						{isMutating && <Spinner size="sm" className="absolute" />}
					</Button>
				</DialogFooter>
			</DialogContent>
		</Dialog>
	);
}
