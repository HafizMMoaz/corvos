"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import type {
	AdminConnectorCredentialRead,
	RevealConnectorCredentialResponse,
	UpdateConnectorCredentialRequest,
} from "@/contracts/types/admin-connectors.types";
import { adminConnectorsApiService } from "@/lib/apis/admin-connectors.service";
import { AppError, AuthorizationError } from "@/lib/error";

export function useAdminConnectors() {
	const [connectors, setConnectors] = useState<AdminConnectorCredentialRead[]>([]);
	const [isLoading, setIsLoading] = useState(true);
	const [isMutating, setIsMutating] = useState(false);

	const refresh = useCallback(async () => {
		setIsLoading(true);
		try {
			const data = await adminConnectorsApiService.getConnectors();
			// GET /admin/connector-credentials returns { connectors }, not a bare
			// array. base-api only logs a schema mismatch (it returns the raw
			// payload rather than throwing), so guard the shape here instead of
			// letting a drifted contract reach the renderer as a non-array.
			if (!Array.isArray(data.connectors)) {
				throw new Error("Unexpected /admin/connector-credentials response shape");
			}
			setConnectors(data.connectors);
		} catch (error) {
			console.error("Failed to load admin connectors:", error);
			toast.error("Failed to load connectors");
		} finally {
			setIsLoading(false);
		}
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	const updateConnector = useCallback(
		async (connectorKey: string, updates: UpdateConnectorCredentialRequest) => {
			setIsMutating(true);
			try {
				await adminConnectorsApiService.updateConnector(connectorKey, updates);
				await refresh();
				toast.success("Connector updated");
			} catch (error) {
				console.error("Failed to update connector:", error);
				toast.error(error instanceof AppError ? error.message : "Failed to update connector");
				throw error;
			} finally {
				setIsMutating(false);
			}
		},
		[refresh]
	);

	const revertConnector = useCallback(
		async (connectorKey: string) => {
			setIsMutating(true);
			try {
				await adminConnectorsApiService.deleteConnector(connectorKey);
				await refresh();
				toast.success("Connector reverted to default");
			} catch (error) {
				console.error("Failed to revert connector:", error);
				toast.error("Failed to revert connector");
				throw error;
			} finally {
				setIsMutating(false);
			}
		},
		[refresh]
	);

	/** Calls the reveal endpoint and returns both decrypted fields; does not touch list state. */
	const revealConnector = useCallback(
		async (connectorKey: string): Promise<RevealConnectorCredentialResponse> => {
			try {
				return await adminConnectorsApiService.revealConnector(connectorKey);
			} catch (error) {
				console.error("Failed to reveal connector:", error);
				if (error instanceof AuthorizationError) {
					toast.error("You don't have permission to reveal these values");
				} else {
					toast.error("Failed to reveal values");
				}
				throw error;
			}
		},
		[]
	);

	return {
		connectors,
		isLoading,
		isMutating,
		refresh,
		updateConnector,
		revertConnector,
		revealConnector,
	};
}
