"use client";

import { useCallback, useEffect, useState } from "react";
import type { AdminMeResponse } from "@/contracts/types/admin-rbac.types";
import { authenticatedFetch } from "@/lib/auth-fetch";
import { buildBackendUrl } from "@/lib/env-config";

type AdminSessionState =
	| { status: "loading"; admin: null }
	| { status: "authenticated"; admin: AdminMeResponse }
	// Logged in, but no platform admin role - distinct from "unauthenticated" so the
	// caller can send the user to /dashboard instead of the login page.
	| { status: "forbidden"; admin: null }
	| { status: "unauthenticated"; admin: null };

/**
 * Resolves whether the current user is a platform admin by calling
 * `GET /api/v1/admin/me`. Mirrors `useSession`'s status shape, but a 403
 * response (logged in, not an admin) is surfaced as its own "forbidden"
 * status rather than being treated the same as "unauthenticated" (no
 * session at all) - callers redirect those two cases differently.
 */
export function useAdminSession() {
	const [state, setState] = useState<AdminSessionState>({ status: "loading", admin: null });

	const refresh = useCallback(async () => {
		try {
			const response = await authenticatedFetch(buildBackendUrl("/api/v1/admin/me"), {
				skipAuthRedirect: true,
			});

			if (response.status === 401) {
				setState({ status: "unauthenticated", admin: null });
				return;
			}

			if (response.status === 403) {
				setState({ status: "forbidden", admin: null });
				return;
			}

			if (!response.ok) {
				setState({ status: "unauthenticated", admin: null });
				return;
			}

			const data = (await response.json()) as AdminMeResponse;
			setState({ status: "authenticated", admin: data });
		} catch {
			setState({ status: "unauthenticated", admin: null });
		}
	}, []);

	useEffect(() => {
		void refresh();
	}, [refresh]);

	return { ...state, refresh };
}
