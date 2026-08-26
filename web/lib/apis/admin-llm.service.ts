import {
	type AdminLlmModelCreateRequest,
	type AdminLlmModelUpdateRequest,
	type AdminLlmProviderCreateRequest,
	type AdminLlmProviderUpdateRequest,
	adminFreeQuotaGlobalRead,
	adminFreeQuotaUserRead,
	adminLlmDiscoveredModelRead,
	adminLlmModelRead,
	adminLlmProviderRead,
	adminLlmProviderRevealResponse,
	adminLlmReloadResponse,
} from "@/contracts/types/admin-llm.types";
import { baseApiService } from "./base-api.service";

/**
 * Thin REST client for the Phase C admin LLM provider/model catalog and
 * free-model quota routes.
 *
 * Kept as the single place that talks to `/api/v1/admin/llm-providers`,
 * `/api/v1/admin/llm-models`, and `/api/v1/admin/llm-quota*`. Request and
 * response shapes are defined in admin-llm.types.ts, which mirrors
 * `backend/app/schemas/admin_llm_schemas.py`.
 */
class AdminLlmApiService {
	// ---- Providers ----

	getProviders = async () => {
		return baseApiService.get(`/api/v1/admin/llm-providers`, adminLlmProviderRead.array());
	};

	createProvider = async (body: AdminLlmProviderCreateRequest) => {
		return baseApiService.post(`/api/v1/admin/llm-providers`, adminLlmProviderRead, { body });
	};

	updateProvider = async (id: number, body: AdminLlmProviderUpdateRequest) => {
		return baseApiService.put(
			`/api/v1/admin/llm-providers/${encodeURIComponent(String(id))}`,
			adminLlmProviderRead,
			{ body }
		);
	};

	deleteProvider = async (id: number) => {
		return baseApiService.delete(`/api/v1/admin/llm-providers/${encodeURIComponent(String(id))}`);
	};

	/** Returns the provider's decrypted plaintext API key. Requires llm_providers:write. */
	revealProviderApiKey = async (id: number) => {
		return baseApiService.post(
			`/api/v1/admin/llm-providers/${encodeURIComponent(String(id))}/reveal`,
			adminLlmProviderRevealResponse
		);
	};

	/**
	 * Fetches the live list of models available from this provider's own API
	 * (or LiteLLM's bundled cost map for `static`-discovery providers).
	 * Requires llm_providers:read.
	 */
	discoverProviderModels = async (providerId: number) => {
		return baseApiService.post(
			`/api/v1/admin/llm-providers/${encodeURIComponent(String(providerId))}/discover-models`,
			adminLlmDiscoveredModelRead.array()
		);
	};

	// ---- Models ----

	getModels = async () => {
		return baseApiService.get(`/api/v1/admin/llm-models`, adminLlmModelRead.array());
	};

	createModel = async (body: AdminLlmModelCreateRequest) => {
		return baseApiService.post(`/api/v1/admin/llm-models`, adminLlmModelRead, { body });
	};

	updateModel = async (id: number, body: AdminLlmModelUpdateRequest) => {
		return baseApiService.put(
			`/api/v1/admin/llm-models/${encodeURIComponent(String(id))}`,
			adminLlmModelRead,
			{ body }
		);
	};

	deleteModel = async (id: number) => {
		return baseApiService.delete(`/api/v1/admin/llm-models/${encodeURIComponent(String(id))}`);
	};

	/** Force-reapplies the DB-backed catalog into the live config; returns the applied count. */
	reloadCatalog = async () => {
		return baseApiService.post(`/api/v1/admin/llm-models/reload`, adminLlmReloadResponse);
	};

	// ---- Free-model quota ----

	getGlobalQuota = async () => {
		return baseApiService.get(`/api/v1/admin/llm-quota`, adminFreeQuotaGlobalRead);
	};

	getUserQuota = async (userId: string) => {
		return baseApiService.get(
			`/api/v1/admin/llm-quota/users/${encodeURIComponent(userId)}`,
			adminFreeQuotaUserRead
		);
	};

	/** Zeroes the platform-wide free-tier counter shared by every user. */
	resetGlobalQuota = async () => {
		return baseApiService.post(`/api/v1/admin/llm-quota/reset`, adminFreeQuotaGlobalRead);
	};

	resetUserQuota = async (userId: string) => {
		return baseApiService.post(
			`/api/v1/admin/llm-quota/users/${encodeURIComponent(userId)}/reset`,
			adminFreeQuotaUserRead
		);
	};
}

export const adminLlmApiService = new AdminLlmApiService();
