import type { Metadata } from "next";
import { ContactFormGridWithDetails } from "@/components/contact/contact-form";

export const metadata: Metadata = {
	title: "Contact | Corvos",
	description:
		"Get in touch with the Corvos team for enterprise AI search, knowledge management, or partnership inquiries.",
	alternates: {
		canonical: "https://www.corvos.com/contact",
	},
};

const page = () => {
	return (
		<div>
			<ContactFormGridWithDetails />
		</div>
	);
};

export default page;
