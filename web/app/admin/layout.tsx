import { RuntimeConfig } from "@/components/providers/runtime-config.server";
import { AdminShell } from "./admin-shell";
import { AdminLayoutShell } from "./layout-shell";

interface AdminLayoutProps {
	children: React.ReactNode;
}

export default function AdminLayout({ children }: AdminLayoutProps) {
	return (
		<RuntimeConfig>
			<AdminShell>
				<AdminLayoutShell>{children}</AdminLayoutShell>
			</AdminShell>
		</RuntimeConfig>
	);
}
