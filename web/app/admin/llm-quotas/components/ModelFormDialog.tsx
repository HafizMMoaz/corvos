"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm, useWatch } from "react-hook-form";
import {
	Accordion,
	AccordionContent,
	AccordionItem,
	AccordionTrigger,
} from "@/components/ui/accordion";
import { Button } from "@/components/ui/button";
import {
	Dialog,
	DialogContent,
	DialogDescription,
	DialogFooter,
	DialogHeader,
	DialogTitle,
} from "@/components/ui/dialog";
import { Form } from "@/components/ui/form";
import { Spinner } from "@/components/ui/spinner";
import type {
	AdminLlmModelCreateRequest,
	AdminLlmModelRead,
	AdminLlmModelUpdateRequest,
	AdminLlmProviderRead,
} from "@/contracts/types/admin-llm.types";
import { useAdminLlmDiscoveredModels } from "@/hooks/use-admin-llm-discovered-models";
import { ModelCapabilityFields } from "./ModelCapabilityFields";
import { ModelIdentityFields } from "./ModelIdentityFields";
import { ModelPromptFields } from "./ModelPromptFields";
import { ModelProviderOverrideFields } from "./ModelProviderOverrideFields";
import { ModelRateLimitFields } from "./ModelRateLimitFields";
import { ModelVisibilityFields } from "./ModelVisibilityFields";
import {
	buildModelPayload,
	EMPTY_MODEL_VALUES,
	type ModelFormValues,
	modelFormSchema,
	modelToFormValues,
} from "./model-form-schema";

const SECTIONS = [
	"identity",
	"visibility",
	"capabilities",
	"rate-limits",
	"provider-overrides",
	"prompt",
];

interface ModelFormDialogProps {
	open: boolean;
	onOpenChange: (open: boolean) => void;
	/** Model being edited, or null when the dialog is in create mode. */
	model: AdminLlmModelRead | null;
	providers: AdminLlmProviderRead[];
	isMutating: boolean;
	onCreate: (body: AdminLlmModelCreateRequest) => Promise<void>;
	onUpdate: (id: number, body: AdminLlmModelUpdateRequest) => Promise<void>;
}

/**
 * Create/edit dialog for a model, grouped into the 6 labeled sections the
 * brief calls out (Identity, Visibility, Capabilities, Rate limits &
 * routing, Provider overrides, Prompt behavior) rather than one flat
 * 24-field list. Each section is its own component; this file only owns
 * form setup, the Accordion shell, and submit/reset wiring.
 */
export function ModelFormDialog({
	open,
	onOpenChange,
	model,
	providers,
	isMutating,
	onCreate,
	onUpdate,
}: ModelFormDialogProps) {
	const isEditing = model !== null;

	const form = useForm<ModelFormValues>({
		resolver: zodResolver(modelFormSchema),
		defaultValues: EMPTY_MODEL_VALUES,
	});

	useEffect(() => {
		if (!open) return;
		form.reset(model ? modelToFormValues(model) : EMPTY_MODEL_VALUES);
	}, [open, model, form.reset]);

	// Live model discovery (Track 4): fetch the discovered model list whenever
	// the selected provider changes, and whenever the dialog opens on an
	// existing model under a known provider. Discovery failing or returning
	// empty must never block manual entry -- ModelIdentityFields renders its
	// own fallback messaging and always keeps free-text entry available.
	const providerId = useWatch({ control: form.control, name: "provider_id" });
	const {
		models: discoveredModels,
		isLoading: isDiscovering,
		error: discoveryError,
		discover,
		reset: resetDiscovery,
	} = useAdminLlmDiscoveredModels();

	useEffect(() => {
		if (!open || !providerId) {
			resetDiscovery();
			return;
		}
		void discover(Number(providerId));
	}, [open, providerId, discover, resetDiscovery]);

	async function handleSubmit(values: ModelFormValues) {
		const payload = buildModelPayload(values);
		try {
			if (isEditing && model) {
				await onUpdate(model.id, payload);
			} else {
				await onCreate(payload);
			}
			onOpenChange(false);
		} catch {
			// hook already surfaced a toast; keep the dialog open to retry
		}
	}

	return (
		<Dialog open={open} onOpenChange={onOpenChange}>
			<DialogContent className="max-h-[85vh] max-w-xl overflow-y-auto">
				<DialogHeader>
					<DialogTitle>{isEditing ? "Edit model" : "Add model"}</DialogTitle>
					<DialogDescription>
						{isEditing
							? "Update this model's configuration."
							: "Add a model under one of the configured providers."}
					</DialogDescription>
				</DialogHeader>

				<Form {...form}>
					<form onSubmit={form.handleSubmit(handleSubmit)} className="space-y-4">
						<Accordion type="multiple" defaultValue={SECTIONS} className="space-y-1">
							<AccordionItem value="identity" className="rounded-md border px-3">
								<AccordionTrigger>Identity</AccordionTrigger>
								<AccordionContent>
									<ModelIdentityFields
										providers={providers}
										isMutating={isMutating}
										discoveredModels={discoveredModels}
										isDiscovering={isDiscovering}
										discoveryError={discoveryError}
									/>
								</AccordionContent>
							</AccordionItem>

							<AccordionItem value="visibility" className="rounded-md border px-3">
								<AccordionTrigger>Visibility</AccordionTrigger>
								<AccordionContent>
									<ModelVisibilityFields isMutating={isMutating} />
								</AccordionContent>
							</AccordionItem>

							<AccordionItem value="capabilities" className="rounded-md border px-3">
								<AccordionTrigger>Capabilities</AccordionTrigger>
								<AccordionContent>
									<ModelCapabilityFields isMutating={isMutating} />
								</AccordionContent>
							</AccordionItem>

							<AccordionItem value="rate-limits" className="rounded-md border px-3">
								<AccordionTrigger>Rate limits & routing</AccordionTrigger>
								<AccordionContent>
									<ModelRateLimitFields isMutating={isMutating} />
								</AccordionContent>
							</AccordionItem>

							<AccordionItem value="provider-overrides" className="rounded-md border px-3">
								<AccordionTrigger>Provider overrides</AccordionTrigger>
								<AccordionContent>
									<ModelProviderOverrideFields isMutating={isMutating} />
								</AccordionContent>
							</AccordionItem>

							<AccordionItem value="prompt" className="rounded-md border px-3">
								<AccordionTrigger>Prompt behavior</AccordionTrigger>
								<AccordionContent>
									<ModelPromptFields isMutating={isMutating} />
								</AccordionContent>
							</AccordionItem>
						</Accordion>

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
									{isEditing ? "Save changes" : "Add model"}
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
