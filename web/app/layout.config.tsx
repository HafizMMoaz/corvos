import type { BaseLayoutProps } from "fumadocs-ui/layouts/shared";
import Image from "next/image";
export const baseOptions: BaseLayoutProps = {
	nav: {
		title: (
			<>
				<Image src="/icon-128.svg" alt="Corvos" width={24} height={24} className="dark:invert" />
				Corvos Docs
			</>
		),
	},
	githubUrl: "https://github.com/HafizMMoaz/Corvos",
};
