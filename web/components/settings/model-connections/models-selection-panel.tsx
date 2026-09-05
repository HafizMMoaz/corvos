import { Plus, RefreshCw } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import {
	capability,
	capabilityLabels,
	MODEL_CAPABILITY_FILTERS,
	type ModelCapabilityFilter,
	modelLabel,
	type SelectableModel,
} from "./model-utils";

interface ModelsSelectionPanelProps {
	models: SelectableModel[];
	description?: string;
	emptyMessage?: string;
	refreshLabel?: string;
	isRefreshing?: boolean;
	isRefreshDisabled?: boolean;
	isUpdatingModel?: boolean;
	isBulkUpdating?: boolean;
	onRefresh?: () => void;
	onToggleModel?: (model: SelectableModel, enabled: boolean) => void;
	onBulkToggle?: (models: SelectableModel[], enabled: boolean) => void;
	/** Some providers (proxies/routers) don't expose a models list endpoint at
	 * all, or it's broken/gated - let the user type the model id directly. */
	onAddManualModel?: (modelId: string) => void;
	isAddingManualModel?: boolean;
}

export function ModelsSelectionPanel({
	models,
	description = "Select models to make available for this provider.",
	emptyMessage = "No models available.",
	refreshLabel = "Refresh models",
	isRefreshing = false,
	isRefreshDisabled = false,
	isUpdatingModel = false,
	isBulkUpdating = false,
	onRefresh,
	onToggleModel,
	onBulkToggle,
	onAddManualModel,
	isAddingManualModel = false,
}: ModelsSelectionPanelProps) {
	const [modelFilter, setModelFilter] = useState<ModelCapabilityFilter | null>(null);
	const [manualModelId, setManualModelId] = useState("");

	function handleAddManualModel() {
		const trimmed = manualModelId.trim();
		if (!trimmed || !onAddManualModel) return;
		onAddManualModel(trimmed);
		setManualModelId("");
	}

	const filteredModels = modelFilter
		? models.filter((model) => capability(model, modelFilter))
		: models;
	const allFilteredModelsEnabled =
		filteredModels.length > 0 && filteredModels.every((model) => model.enabled);

	function toggleFilteredModels() {
		const nextEnabled = !allFilteredModelsEnabled;
		const changedModels = filteredModels.filter((model) => model.enabled !== nextEnabled);
		if (changedModels.length === 0) return;
		onBulkToggle?.(changedModels, nextEnabled);
	}

	return (
		<div className="space-y-3">
			<div className="flex flex-wrap items-start justify-between gap-3">
				<div>
					<div className="font-semibold">Models</div>
					<p className="text-sm text-muted-foreground">{description}</p>
				</div>
				<div className="flex flex-wrap items-center gap-2">
					<Button
						variant="ghost"
						size="sm"
						type="button"
						onClick={toggleFilteredModels}
						disabled={!onBulkToggle || isBulkUpdating || filteredModels.length === 0}
					>
						{allFilteredModelsEnabled ? "Deselect All" : "Select All"}
					</Button>
					{onRefresh ? (
						<Button
							variant="ghost"
							size="icon"
							type="button"
							onClick={onRefresh}
							disabled={isRefreshing || isRefreshDisabled}
							aria-label={refreshLabel}
						>
							<RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
						</Button>
					) : null}
				</div>
			</div>

			{onAddManualModel ? (
				<div className="flex items-center gap-2">
					<Input
						value={manualModelId}
						onChange={(event) => setManualModelId(event.target.value)}
						onKeyDown={(event) => {
							if (event.key === "Enter") {
								event.preventDefault();
								handleAddManualModel();
							}
						}}
						placeholder="Add a model by id, e.g. gpt-5.5 (for providers without model listing)"
						disabled={isAddingManualModel}
						className="h-9"
					/>
					<Button
						type="button"
						variant="secondary"
						size="sm"
						className="h-9 shrink-0 gap-1"
						onClick={handleAddManualModel}
						disabled={!manualModelId.trim() || isAddingManualModel}
					>
						{isAddingManualModel ? <Spinner size="sm" /> : <Plus className="h-4 w-4" />}
						Add
					</Button>
				</div>
			) : null}

			{models.length > 0 ? (
				<div className="flex flex-wrap items-center gap-2">
					<span className="text-xs font-medium text-muted-foreground">Filter models</span>
					{MODEL_CAPABILITY_FILTERS.map((filter) => {
						const count = models.filter((model) => capability(model, filter.key)).length;
						const isActive = modelFilter === filter.key;

						return (
							<Button
								key={filter.key}
								type="button"
								variant="secondary"
								size="sm"
								className={`h-7 rounded-full px-3 text-xs ${
									isActive ? "bg-brand text-white hover:bg-brand/90" : "opacity-80"
								}`}
								onClick={() => setModelFilter(isActive ? null : filter.key)}
							>
								{filter.label}
								<span className={`ml-1 ${isActive ? "text-white/80" : "text-muted-foreground"}`}>
									{count}
								</span>
							</Button>
						);
					})}
				</div>
			) : null}

			<div
				className={`overflow-y-auto rounded-xl border bg-muted/20 p-2 ${
					models.length === 0 ? "h-auto border-dashed border-border/100" : "h-80"
				}`}
			>
				{models.length === 0 ? (
					<div className="flex flex-col items-center gap-3 rounded-lg px-3 py-6 text-center text-sm text-muted-foreground">
						{emptyMessage}
						{onRefresh ? (
							<Button
								variant="secondary"
								size="sm"
								type="button"
								onClick={onRefresh}
								disabled={isRefreshing || isRefreshDisabled}
								className="relative"
							>
								<span className={isRefreshing ? "opacity-0" : ""}>Reload models</span>
								{isRefreshing ? <Spinner size="sm" className="absolute" /> : null}
							</Button>
						) : null}
					</div>
				) : null}
				{filteredModels.length === 0 && modelFilter ? (
					<div className="rounded-lg px-3 py-6 text-center text-sm text-muted-foreground">
						No{" "}
						{MODEL_CAPABILITY_FILTERS.find(
							(filter) => filter.key === modelFilter
						)?.label.toLowerCase()}{" "}
						models found on this connection.
					</div>
				) : null}
				<div className="space-y-2">
					{filteredModels.map((model) => (
						<div
							key={model.id ?? model.model_id}
							className="flex items-center gap-3 rounded-lg px-3 py-2 transition-colors hover:bg-popover"
						>
							<Checkbox
								checked={model.enabled}
								onCheckedChange={(checked) => onToggleModel?.(model, checked === true)}
								disabled={!onToggleModel || isUpdatingModel}
								className="border-muted-foreground/20"
							/>
							<div className="min-w-0 flex-1">
								<div className="flex items-center gap-2 text-sm font-medium">
									<span className="truncate">{modelLabel(model)}</span>
								</div>
								<div className="text-xs text-muted-foreground">
									{capabilityLabels(model) || "No discovered capabilities"}
								</div>
							</div>
						</div>
					))}
				</div>
			</div>
		</div>
	);
}
