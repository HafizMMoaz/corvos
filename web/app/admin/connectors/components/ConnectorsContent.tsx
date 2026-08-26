"use client";

import { useMemo } from "react";
import { Skeleton } from "@/components/ui/skeleton";
import { useAdminConnectors } from "@/hooks/use-admin-connectors";
import { ConnectorRow } from "./ConnectorRow";

export function ConnectorsContent() {
	const { connectors, isLoading, isMutating, updateConnector, revertConnector, revealConnector } =
		useAdminConnectors();

	const sorted = useMemo(
		() => [...connectors].sort((a, b) => a.display_name.localeCompare(b.display_name)),
		[connectors]
	);

	return (
		<div className="space-y-6 min-w-0">
			<div>
				<h3 className="text-sm font-semibold tracking-tight">Connector credentials</h3>
				<p className="text-xs text-muted-foreground">
					OAuth app client ID and client secret pairs for each connector integration. Values stay
					masked until revealed.
				</p>
			</div>

			{isLoading ? (
				<div className="space-y-2">
					{["skeleton-a", "skeleton-b", "skeleton-c", "skeleton-d"].map((key) => (
						<Skeleton key={key} className="h-20 w-full" />
					))}
				</div>
			) : (
				<div className="grid grid-cols-1 gap-3">
					{sorted.map((connector) => (
						<ConnectorRow
							key={connector.connector_key}
							connector={connector}
							isMutating={isMutating}
							onUpdate={updateConnector}
							onRevert={revertConnector}
							onReveal={revealConnector}
						/>
					))}
				</div>
			)}
		</div>
	);
}
