import type { Metadata } from "next";
import type { ReactNode } from "react";

export const metadata: Metadata = {
	title: "What's New | Corvos",
	description: "Latest product updates, feature releases, and news from Corvos.",
	alternates: {
		canonical: "https://www.corvos.com/announcements",
	},
	openGraph: {
		title: "What's New | Corvos",
		description: "Latest product updates, feature releases, and news from Corvos.",
		url: "https://www.corvos.com/announcements",
		type: "website",
	},
	twitter: {
		card: "summary_large_image",
		title: "What's New | Corvos",
		description: "Latest product updates, feature releases, and news from Corvos.",
	},
};

export default function AnnouncementsLayout({ children }: { children: ReactNode }) {
	return <>{children}</>;
}
