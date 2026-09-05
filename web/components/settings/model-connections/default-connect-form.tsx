import { useEffect, useState } from "react";
import { ApiBaseUrlField, ApiKeyField } from "./connect-fields";
import type { ProviderConnectFormProps } from "./provider-metadata";

const OPTIONAL_API_KEY_PROVIDERS = new Set(["ollama_chat", "lm_studio", "openai_compatible"]);

function baseUrlHint(provider: string) {
	if (provider === "ollama_chat" || provider === "lm_studio") {
		return "For local servers, use host.docker.internal instead of localhost.";
	}
	if (provider === "openai_compatible") {
		return "Enter the full endpoint URL. This provider expects a /v1-compatible endpoint.";
	}
	if (provider === "openai_compatible_raw") {
		return "Enter the exact chat-completions API base URL. Corvos will not append /v1.";
	}
	if (provider === "gemini") {
		return "Leave blank to use Google AI Studio directly. Include the /v1beta path if you route through a proxy or gateway.";
	}
	if (
		provider === "openai" ||
		provider === "anthropic" ||
		provider === "openrouter" ||
		provider === "requesty"
	) {
		return "Override only if you route through a proxy or gateway.";
	}
	return undefined;
}

/** Ghost placeholder only - never used to prefill the actual submitted value. */
function baseUrlPlaceholder(provider: string, defaultBaseUrl: string) {
	if (provider === "gemini") {
		return "https://generativelanguage.googleapis.com";
	}
	return defaultBaseUrl;
}

/**
 * Connect form for OpenAI-compatible / native key providers (OpenAI, Anthropic,
 * OpenRouter, OpenAI-Compatible, LM Studio, Ollama, …). The base URL is
 * prefilled from the provider default.
 */
export function DefaultConnectForm({
	provider,
	defaultBaseUrl,
	baseUrlRequired,
	onDraftChange,
}: ProviderConnectFormProps) {
	const [baseUrl, setBaseUrl] = useState(defaultBaseUrl);
	const [apiKey, setApiKey] = useState("");
	const isApiKeyOptional = OPTIONAL_API_KEY_PROVIDERS.has(provider);
	const hint = baseUrlHint(provider);
	const apiKeyValue = apiKey.trim();
	const canSubmit =
		!(baseUrlRequired && !baseUrl.trim()) && (isApiKeyOptional || Boolean(apiKeyValue));

	useEffect(() => {
		onDraftChange(
			{ base_url: baseUrl || null, api_key: apiKeyValue || null, extra: {} },
			canSubmit
		);
	}, [apiKeyValue, baseUrl, canSubmit, onDraftChange]);

	return (
		<div className="flex flex-col gap-4">
			<ApiBaseUrlField
				value={baseUrl}
				onChange={setBaseUrl}
				placeholder={baseUrlPlaceholder(provider, defaultBaseUrl)}
				hint={hint}
			/>
			<ApiKeyField
				value={apiKey}
				onChange={setApiKey}
				label={isApiKeyOptional ? "API Key (optional)" : "API Key"}
				placeholder="Enter your API key"
			/>
		</div>
	);
}
