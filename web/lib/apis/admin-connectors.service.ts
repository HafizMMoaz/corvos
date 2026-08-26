import {
	adminConnectorCredentialsListResponse,
	deleteConnectorCredentialResponse,
	revealConnectorCredentialResponse,
	type UpdateConnectorCredentialRequest,
	updateConnectorCredentialRequest,
	updateConnectorCredentialResponse,
} from "@/contracts/types/admin-connectors.types";
import { ValidationError } from "../error";
import { baseApiService } from "./base-api.service";

/**
 * Thin REST client for the Phase D admin connector credentials vault routes.
 *
 * Kept as the single place that talks to `/api/v1/admin/connector-credentials/*`.
 * Request and response shapes are defined in admin-connectors.types.ts, which
 * mirrors `backend/app/schemas/admin_connector_credentials_schemas.py`.
 */
class AdminConnectorsApiService {
	getConnectors = async () => {
		return baseApiService.get(
			`/api/v1/admin/connector-credentials`,
			adminConnectorCredentialsListResponse
		);
	};

	revealConnector = async (connectorKey: string) => {
		return baseApiService.post(
			`/api/v1/admin/connector-credentials/${encodeURIComponent(connectorKey)}/reveal`,
			revealConnectorCredentialResponse
		);
	};

	/**
	 * Partial update. `updates` should only contain the keys actually being
	 * changed -- build it with plain object-literal field omission (never set
	 * a key to `undefined` explicitly if you mean "don't send it"; JS object
	 * literals and `JSON.stringify` both drop keys whose value is the literal
	 * `undefined`, which is exactly the mechanism this relies on). Passing
	 * `null` for a field explicitly clears it.
	 */
	updateConnector = async (connectorKey: string, updates: UpdateConnectorCredentialRequest) => {
		const parsed = updateConnectorCredentialRequest.safeParse(updates);
		if (!parsed.success) {
			console.error("Invalid request:", parsed.error);
			const errorMessage = parsed.error.issues.map((issue) => issue.message).join(", ");
			throw new ValidationError(`Invalid request: ${errorMessage}`);
		}
		return baseApiService.put(
			`/api/v1/admin/connector-credentials/${encodeURIComponent(connectorKey)}`,
			updateConnectorCredentialResponse,
			{ body: parsed.data }
		);
	};

	/** Reverts the connector to its default (deletes the DB override row). */
	deleteConnector = async (connectorKey: string) => {
		return baseApiService.delete(
			`/api/v1/admin/connector-credentials/${encodeURIComponent(connectorKey)}`,
			deleteConnectorCredentialResponse
		);
	};
}

export const adminConnectorsApiService = new AdminConnectorsApiService();
