"use client";

import { useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import type { AdminMeResponse } from "@/contracts/types/admin-rbac.types";
import { useAdminSession } from "@/hooks/use-admin-session";
import { useGlobalLoadingEffect } from "@/hooks/use-global-loading";
import { redirectToLogin } from "@/lib/auth-utils";

const AdminSessionContext = createContext<AdminMeResponse | null>(null);

/**
 * The signed-in admin's effective platform permissions, as already resolved
 * once by AdminShell's `/admin/me` call - so pages can gate their controls
 * without each refetching the session.
 *
 * Gating here is a UX affordance, not a security boundary: every admin route
 * re-checks the same permission server-side and 403s regardless.
 */
export function useAdminPermissions() {
	const admin = useContext(AdminSessionContext);

	return useMemo(() => {
		const granted = new Set(admin?.permissions ?? []);
		return {
			permissions: admin?.permissions ?? [],
			// "*" is PlatformPermission.FULL_ACCESS (the super_admin grant);
			// mirrors has_permission() in backend/app/db.py.
			has: (permission: string) => granted.has("*") || granted.has(permission),
		};
	}, [admin]);
}

export function AdminShell({ children }: { children: React.ReactNode }) {
	const [isCheckingAuth, setIsCheckingAuth] = useState(true);
	const session = useAdminSession();
	const router = useRouter();

	// Use the global loading screen - spinner animation won't reset
	useGlobalLoadingEffect(isCheckingAuth);

	useEffect(() => {
		if (session.status === "loading") return;

		if (session.status === "unauthenticated") {
			redirectToLogin();
			return;
		}

		if (session.status === "forbidden") {
			toast.error("You don't have access to the admin dashboard");
			router.replace("/dashboard");
			return;
		}

		setIsCheckingAuth(false);
	}, [session.status, router]);

	// Return null while loading/redirecting - the global provider handles the loading UI
	if (isCheckingAuth || session.status !== "authenticated") {
		return null;
	}

	return (
		<AdminSessionContext.Provider value={session.admin}>
			<div className="h-full flex flex-col">{children}</div>
		</AdminSessionContext.Provider>
	);
}
