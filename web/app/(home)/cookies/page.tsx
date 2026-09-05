import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
	title: "Cookie Policy | Corvos",
	description: "Cookie Policy for Corvos. Learn which cookies we use and how to control them.",
	alternates: {
		canonical: "https://www.Corvos.com/cookies",
	},
};

const LAST_UPDATED = "July 31, 2026";

export default function CookiePolicy() {
	return (
		<div className="container max-w-4xl mx-auto py-12 px-4">
			<h1 className="text-4xl font-bold mb-8">Cookie Policy</h1>

			<div className="prose dark:prose-invert max-w-none">
				<p className="text-lg mb-6">Last updated: {LAST_UPDATED}</p>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">1. What Are Cookies</h2>
					<p>
						Cookies are small text files placed on your device when you visit a website. We also use
						similar technologies such as local storage and session storage. This Cookie Policy
						explains what we use on <a href="https://www.Corvos.com">www.Corvos.com</a> and the
						Corvos application (the "Service") and how you can control them. It should be read
						alongside our <Link href="/privacy">Privacy Policy</Link>.
					</p>
					<p className="mt-4">
						We do not run advertising on the Service and do not use advertising or tracking cookies
						from ad networks.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">2. Cookies We Use</h2>
					<div className="overflow-x-auto">
						<table className="w-full border-collapse text-left text-sm">
							<thead>
								<tr className="border-b">
									<th className="py-2 pr-4">Category</th>
									<th className="py-2 pr-4">Purpose</th>
									<th className="py-2">Can you opt out?</th>
								</tr>
							</thead>
							<tbody>
								<tr className="border-b align-top">
									<td className="py-2 pr-4 font-medium">Strictly necessary</td>
									<td className="py-2 pr-4">
										Authentication, session management, and security (including CAPTCHA/anti-abuse
										via Cloudflare Turnstile). Required for the Service to function.
									</td>
									<td className="py-2">No - blocking these breaks sign-in and core features.</td>
								</tr>
								<tr className="border-b align-top">
									<td className="py-2 pr-4 font-medium">Preference</td>
									<td className="py-2 pr-4">
										Remembers choices such as theme (light/dark) and onboarding state.
									</td>
									<td className="py-2">Yes, via your browser settings.</td>
								</tr>
								<tr className="align-top">
									<td className="py-2 pr-4 font-medium">Analytics</td>
									<td className="py-2 pr-4">
										Helps us understand how the Service is used so we can improve it. We use{" "}
										<a href="https://posthog.com/privacy">PostHog</a> for product analytics.
									</td>
									<td className="py-2">
										Yes, via your browser settings or a tracking-blocker extension.
									</td>
								</tr>
							</tbody>
						</table>
					</div>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">3. Third-Party Cookies</h2>
					<p>
						Some cookies are set by services we embed, not by Corvos directly: Cloudflare Turnstile
						(security) and PostHog (analytics). Each provider's own privacy policy governs how it
						processes data collected through its cookies.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">4. Managing Cookies</h2>
					<p>
						Most browsers let you view, delete, and block cookies through their settings. Blocking
						strictly necessary cookies will prevent the Service from functioning correctly (for
						example, you won't be able to stay signed in). You can also install a browser extension
						that blocks analytics scripts if you'd prefer we not receive usage data.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">5. Changes to This Policy</h2>
					<p>
						We may update this Cookie Policy from time to time to reflect changes in the cookies we
						use or for legal reasons. Material changes will be reflected by updating the "Last
						updated" date above.
					</p>
				</section>

				<section className="mb-8">
					<h2 className="text-2xl font-semibold mb-4">6. Contact Us</h2>
					<p>If you have questions about this Cookie Policy, please contact us at:</p>
					<p className="mt-2">
						<strong>Email:</strong>{" "}
						<a href="mailto:hafizmoazkhalid@gmail.com">hafizmoazkhalid@gmail.com</a>
					</p>
				</section>
			</div>
		</div>
	);
}
