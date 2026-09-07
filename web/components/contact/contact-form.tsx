"use client";
import { IconCalendar, IconMailFilled } from "@tabler/icons-react";
import Link from "next/link";
import type React from "react";
import { useId } from "react";
import { cn } from "@/lib/utils";

export function ContactFormGridWithDetails() {
	return (
		<div className="mx-auto flex w-full max-w-7xl flex-col items-center gap-10 px-4 py-10 md:px-6 md:py-20">
			<div className="relative flex flex-col items-center overflow-hidden">
				<div className="flex items-start justify-start">
					<FeatureIconContainer className="flex items-center justify-center overflow-hidden">
						<IconMailFilled className="h-6 w-6 text-blue-500" />
					</FeatureIconContainer>
				</div>
				<h1 className="mt-9 bg-gradient-to-b from-neutral-800 to-neutral-900 bg-clip-text text-center text-xl font-bold text-transparent md:text-3xl lg:text-5xl dark:from-neutral-200 dark:to-neutral-300">
					Contact
				</h1>
				<p className="mt-8 max-w-lg text-center text-base text-neutral-600 dark:text-neutral-400">
					We'd love to hear from you!
				</p>
				<p className="mt-4 max-w-lg text-center text-base text-neutral-600 dark:text-neutral-400">
					Schedule a meeting with us, or send us an email.
				</p>

				<div className="mt-10 flex flex-col items-center gap-6">
					<Link
						href=""
						target="_blank"
						rel="noopener noreferrer"
						className="flex items-center gap-3 rounded-xl bg-gradient-to-b from-blue-500 to-blue-600 px-6 py-3 text-base font-medium text-white shadow-lg transition duration-200 hover:from-blue-600 hover:to-blue-700"
					>
						<IconCalendar className="h-5 w-5" />
						Schedule a Meeting
					</Link>

					<div className="flex items-center gap-2 text-neutral-500 dark:text-neutral-400">
						<span className="h-px w-8 bg-neutral-300 dark:bg-neutral-600" />
						<span className="text-sm">or</span>
						<span className="h-px w-8 bg-neutral-300 dark:bg-neutral-600" />
					</div>

					<Link
						href="mailto:hafizmoazkhalid@gmail.com"
						className="flex items-center gap-2 text-base text-neutral-600 transition duration-200 hover:text-neutral-900 dark:text-neutral-400 dark:hover:text-neutral-200"
					>
						<IconMailFilled className="h-5 w-5" />
						hafizmoazkhalid@gmail.com
					</Link>
				</div>
			</div>
		</div>
	);
}

export const FeatureIconContainer = ({
	children,
	className,
}: {
	children: React.ReactNode;
	className?: string;
}) => {
	return (
		<div
			className={cn(
				"relative h-14 w-14 rounded-md bg-gradient-to-b from-gray-50 to-neutral-200 p-[4px] dark:from-neutral-800 dark:to-neutral-950",
				className
			)}
		>
			<div
				className={cn(
					"relative z-20 h-full w-full rounded-[5px] bg-gray-50 dark:bg-neutral-800",
					className
				)}
			>
				{children}
			</div>
			<div className="absolute inset-x-0 bottom-0 z-30 mx-auto h-4 w-full rounded-full bg-neutral-600 opacity-50 blur-lg"></div>
			<div className="absolute inset-x-0 bottom-0 mx-auto h-px w-[60%] bg-gradient-to-r from-transparent via-blue-500 to-transparent"></div>
			<div className="absolute inset-x-0 bottom-0 mx-auto h-px w-[60%] bg-gradient-to-r from-transparent via-blue-600 to-transparent dark:h-[8px] dark:blur-sm"></div>
		</div>
	);
};

export const Grid = ({ pattern, size }: { pattern?: [number, number][]; size?: number }) => {
	const p = pattern ?? [
		[9, 3],
		[8, 5],
		[10, 2],
		[7, 4],
		[9, 6],
	];
	return (
		<div className="pointer-events-none absolute top-0 left-1/2 -mt-2 -ml-20 h-full w-full [mask-image:linear-gradient(white,transparent)]">
			<div className="absolute inset-0 bg-gradient-to-r from-zinc-900/30 to-zinc-900/30 opacity-10 [mask-image:radial-gradient(farthest-side_at_top,white,transparent)] dark:from-zinc-900/30 dark:to-zinc-900/30">
				<GridPattern
					width={size ?? 20}
					height={size ?? 20}
					x="-12"
					y="4"
					squares={p}
					className="absolute inset-0 h-full w-full fill-black/100 stroke-black/100 mix-blend-overlay dark:fill-white/100 dark:stroke-white/100"
				/>
			</div>
		</div>
	);
};

export function GridPattern({
	width,
	height,
	x,
	y,
	squares,
	...props
}: React.ComponentProps<"svg"> & {
	width: number;
	height: number;
	x: string | number;
	y: string | number;
	squares?: [number, number][];
}) {
	const patternId = useId();

	return (
		<svg aria-hidden="true" {...props}>
			<defs>
				<pattern
					id={patternId}
					width={width}
					height={height}
					patternUnits="userSpaceOnUse"
					x={x}
					y={y}
				>
					<path d={`M.5 ${height}V.5H${width}`} fill="none" />
				</pattern>
			</defs>
			<rect width="100%" height="100%" strokeWidth={0} fill={`url(#${patternId})`} />
			{squares && (
				<svg aria-hidden="true" x={x} y={y} className="overflow-visible">
					{squares.map(([x, y]: [number, number], idx: number) => (
						<rect
							strokeWidth="0"
							key={`${x}-${y}-${idx}`}
							width={width + 1}
							height={height + 1}
							x={x * width}
							y={y * height}
						/>
					))}
				</svg>
			)}
		</svg>
	);
}
