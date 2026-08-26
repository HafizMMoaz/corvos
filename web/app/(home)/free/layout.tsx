import type { ReactNode } from "react";

/** Wraps the /free hub and all /free/[model_slug] subpages. */
export default function FreeSectionLayout({ children }: { children: ReactNode }) {
	return <>{children}</>;
}
