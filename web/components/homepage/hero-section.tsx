"use client";
import {
	IconBrandAmazon,
	IconBrandGithub,
	IconBrandGoogle,
	IconBrandInstagram,
	IconBrandReddit,
	IconBrandTiktok,
	IconBrandYoutube,
	IconBriefcase,
	IconMapPin,
	IconSearch,
} from "@tabler/icons-react";
import { ChevronDown, Download } from "lucide-react";
import {
	AnimatePresence,
	motion,
	useAnimationFrame,
	useMotionValue,
	useReducedMotion,
} from "motion/react";
import Link from "next/link";
import React, { memo, useCallback, useEffect, useRef, useState } from "react";
import Balancer from "react-wrap-balancer";
import { HeroChatDemo, type HeroChatDemoScript } from "@/components/homepage/hero-chat-demo";
import { Button } from "@/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { ExpandedMediaOverlay, useExpandedMedia } from "@/components/ui/expanded-gif-overlay";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
	GITHUB_RELEASES_URL,
	getAssetLabel,
	usePrimaryDownload,
} from "@/lib/desktop-download-utils";
import { buildBackendUrl } from "@/lib/env-config";
import { trackLoginAttempt } from "@/lib/posthog/events";
import { cn } from "@/lib/utils";

const GoogleLogo = ({ className }: { className?: string }) => (
	<svg
		className={className}
		viewBox="0 0 24 24"
		xmlns="http://www.w3.org/2000/svg"
		role="img"
		aria-label="Google logo"
	>
		<title>Google logo</title>
		<path
			d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
			fill="#4285F4"
		/>
		<path
			d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
			fill="#34A853"
		/>
		<path
			d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
			fill="#FBBC05"
		/>
		<path
			d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
			fill="#EA4335"
		/>
	</svg>
);

type HeroUseCase = {
	id: string;
	title: string;
	description: string;
	src: string | null;
	/** Scripted chat demo shown when there is no recorded video. */
	demo?: HeroChatDemoScript;
};

type HeroCategory = {
	id: string;
	label: string;
	useCases: HeroUseCase[];
};

const FLOATING_ICONS = [
	{
		name: "GitHub",
		Icon: IconBrandGithub,
		color: "#181717",
		startX: 5,
		startY: 18,
		wander: 100,
		delay: 0,
		bobAmp: 8,
		bobDur: 3.5,
	},
	{
		name: "Google",
		Icon: IconBrandGoogle,
		color: "#4285F4",
		startX: 45,
		startY: 15,
		wander: 90,
		delay: 1.5,
		bobAmp: 10,
		bobDur: 4,
	},
	{
		name: "YouTube",
		Icon: IconBrandYoutube,
		color: "#FF0000",
		startX: 80,
		startY: 20,
		wander: 35,
		delay: 0.8,
		bobAmp: 6,
		bobDur: 3,
	},
	{
		name: "Reddit",
		Icon: IconBrandReddit,
		color: "#FF4500",
		startX: 6,
		startY: 42,
		wander: 45,
		delay: 2,
		bobAmp: 9,
		bobDur: 3.8,
	},
	{
		name: "Instagram",
		Icon: IconBrandInstagram,
		color: "#E4405F",
		startX: 1,
		startY: 68,
		wander: 40,
		delay: 0.3,
		bobAmp: 7,
		bobDur: 3.2,
	},
	{
		name: "TikTok",
		Icon: IconBrandTiktok,
		color: "#000000",
		startX: 92,
		startY: 38,
		wander: 45,
		delay: 1.2,
		bobAmp: 8,
		bobDur: 4.2,
	},
	{
		name: "Maps",
		Icon: IconMapPin,
		color: "#34A853",
		startX: 90,
		startY: 62,
		wander: 40,
		delay: 2.5,
		bobAmp: 7,
		bobDur: 3.5,
	},
	{
		name: "SERP",
		Icon: IconSearch,
		color: "#4285F4",
		startX: 20,
		startY: 88,
		wander: 35,
		delay: 0.5,
		bobAmp: 6,
		bobDur: 3,
	},
	{
		name: "Indeed",
		Icon: IconBriefcase,
		color: "#2164F3",
		startX: 55,
		startY: 80,
		wander: 45,
		delay: 1.8,
		bobAmp: 10,
		bobDur: 4.5,
	},
	{
		name: "Amazon",
		Icon: IconBrandAmazon,
		color: "#FF9900",
		startX: 78,
		startY: 85,
		wander: 40,
		delay: 0.7,
		bobAmp: 7,
		bobDur: 3.3,
	},
];

function randomBetween(min: number, max: number): number {
	return Math.random() * (max - min) + min;
}

function lerp(a: number, b: number, t: number): number {
	return a + (b - a) * t;
}

function easeInOut(t: number): number {
	return t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2;
}

function FloatingIcon({ icon }: { icon: (typeof FLOATING_ICONS)[number] }) {
	const reduceMotion = useReducedMotion();
	const x = useMotionValue(0);
	const y = useMotionValue(0);
	const rotate = useMotionValue(0);
	const scale = useMotionValue(1);

	const targetRef = useRef({ x: 0, y: 0, rotate: 0, scale: 1 });
	const prevRef = useRef({ x: 0, y: 0, rotate: 0, scale: 1 });
	const progressRef = useRef(0);
	const durationRef = useRef(60);
	const elapsedRef = useRef(0);
	const startedRef = useRef(false);
	const lastTimeRef = useRef(0);

	useAnimationFrame(() => {
		if (reduceMotion) return;

		const now = performance.now();
		if (lastTimeRef.current === 0) {
			lastTimeRef.current = now;
			return;
		}
		const delta = Math.min((now - lastTimeRef.current) / 1000, 0.1);
		lastTimeRef.current = now;

		elapsedRef.current += delta;
		if (elapsedRef.current < icon.delay) return;

		if (!startedRef.current) {
			startedRef.current = true;
			targetRef.current = {
				x: randomBetween(-icon.wander, icon.wander),
				y: randomBetween(-icon.wander, icon.wander),
				rotate: randomBetween(-4, 4),
				scale: randomBetween(0.98, 1.04),
			};
			durationRef.current = randomBetween(40, 80);
		}

		progressRef.current += delta / durationRef.current;

		if (progressRef.current >= 1) {
			prevRef.current = { ...targetRef.current };
			targetRef.current = {
				x: randomBetween(-icon.wander, icon.wander),
				y: randomBetween(-icon.wander, icon.wander),
				rotate: randomBetween(-4, 4),
				scale: randomBetween(0.98, 1.04),
			};
			progressRef.current = 0;
			durationRef.current = randomBetween(40, 80);
		}

		const t = progressRef.current;
		const eased = easeInOut(t);

		const cx = lerp(prevRef.current.x, targetRef.current.x, eased);
		const cy = lerp(prevRef.current.y, targetRef.current.y, eased);
		const cr = lerp(prevRef.current.rotate, targetRef.current.rotate, eased);
		const cs = lerp(prevRef.current.scale, targetRef.current.scale, eased);

		const time = elapsedRef.current;
		const curveX = Math.sin(time * 0.15 + icon.delay) * 8;
		const curveY = Math.cos(time * 0.12 + icon.delay * 1.5) * 8;
		const bobY = Math.sin((time * 2 * Math.PI) / icon.bobDur + icon.delay) * icon.bobAmp;

		x.set(cx + curveX);
		y.set(cy + curveY + bobY);
		rotate.set(cr);
		scale.set(cs);
	});

	const Icon = icon.Icon;

	return (
		<motion.div
			className="absolute"
			style={{ left: `${icon.startX}%`, top: `${icon.startY}%`, x, y, rotate, scale }}
		>
			<div className="relative flex size-14 items-center justify-center">
				<div
					className="absolute inset-0 rounded-full blur-xl"
					style={{ backgroundColor: icon.color, opacity: 0.08 }}
					aria-hidden="true"
				/>
				<Icon className="relative size-10 text-neutral-500/25 dark:text-neutral-400/30 [filter:blur(0.4px)]" />
			</div>
		</motion.div>
	);
}

function FloatingIcons() {
	const [mounted, setMounted] = useState(false);
	useEffect(() => setMounted(true), []);
	if (!mounted) return null;
	return (
		<div className="pointer-events-none absolute inset-0 overflow-hidden">
			{FLOATING_ICONS.map((icon) => (
				<FloatingIcon key={icon.name} icon={icon} />
			))}
		</div>
	);
}

export function HeroSection() {
	return (
		<div className="relative mx-auto flex min-h-screen w-full max-w-7xl min-w-0 flex-col items-center justify-center overflow-hidden px-2 pt-36 md:px-8 xl:px-0">
			<FloatingIcons />
			<div className="relative z-10 flex w-full min-w-0 flex-col items-center text-center">
				<h1
					className={cn(
						"relative mx-auto mt-4 max-w-4xl text-center text-4xl font-bold tracking-tight text-balance text-neutral-900 sm:text-5xl md:text-6xl dark:text-neutral-50"
					)}
				>
					<Balancer>Give your AI agents the live web.</Balancer>
				</h1>
				<div className="mt-4 flex w-full flex-col items-center gap-4 md:mt-8 md:gap-10">
					<div className="flex flex-col items-center">
						<p
							className={cn(
								"relative mb-8 mx-auto max-w-2xl text-center text-sm text-neutral-600 antialiased sm:text-base md:text-lg dark:text-neutral-400"
							)}
						>
							Corvos is the open-source NotebookLM alternative for open web research. Typed
							connectors turn the platforms where answers actually live into structured JSON, so you
							and your agents work from what the web says right now, through one platform, API, or
							MCP server.
						</p>

						<div className="relative mb-4 flex w-full flex-col justify-center gap-y-2 sm:flex-row sm:justify-center sm:space-y-0 sm:space-x-4">
							<GetStartedButton />
							<DownloadButton />
						</div>
					</div>
				</div>
			</div>
		</div>
	);
}

function GetStartedButton() {
	const [isRedirecting, setIsRedirecting] = useState(false);

	const handleGoogleLogin = () => {
		if (isRedirecting) return;
		setIsRedirecting(true);
		trackLoginAttempt("google");
		window.location.href = buildBackendUrl("/auth/google/authorize-redirect");
	};

	return (
		<>
			<Button
				type="button"
				variant="ghost"
				onClick={handleGoogleLogin}
				disabled={isRedirecting}
				className="runtime-auth-google h-14 w-full cursor-pointer gap-3 rounded-lg border border-white bg-white text-center text-base font-medium text-[#1f1f1f] shadow-sm transition duration-150 hover:bg-zinc-100 hover:text-[#1f1f1f] sm:w-56 dark:border-white"
			>
				<GoogleLogo className="h-5 w-5" />
				<span>Continue with Google</span>
			</Button>
			<Button
				asChild
				variant="ghost"
				className="runtime-auth-local h-14 w-full rounded-lg bg-black text-center text-base font-medium text-white shadow-sm ring-1 shadow-black/10 ring-black/10 transition duration-150 active:scale-98 hover:bg-black sm:w-52 dark:bg-white dark:text-black dark:hover:bg-white"
			>
				<Link href="/login">Get Started</Link>
			</Button>
		</>
	);
}

function DownloadButton() {
	const { os, primary, alternatives, isMobileOS } = usePrimaryDownload();

	const fallbackUrl = GITHUB_RELEASES_URL;
	const mobileDisabledLabel = "Desktop app unavailable on mobile";

	if (isMobileOS) {
		return (
			<Button
				type="button"
				variant="ghost"
				disabled
				className="h-14 w-full gap-2 rounded-lg border border-neutral-200 bg-white text-center text-base font-medium text-neutral-700 shadow-sm transition duration-150 sm:w-auto sm:px-6 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200"
			>
				<Download className="size-4" />
				{mobileDisabledLabel}
			</Button>
		);
	}

	if (!primary) {
		return (
			<Button
				asChild
				variant="ghost"
				className="h-14 w-full gap-2 rounded-lg border border-neutral-200 bg-white text-center text-base font-medium text-neutral-700 shadow-sm transition duration-150 active:scale-98 hover:bg-neutral-50 sm:w-auto sm:px-6 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200 dark:hover:bg-neutral-800"
			>
				<a href={fallbackUrl} target="_blank" rel="noopener noreferrer">
					<Download className="size-4" />
					Download for {os}
				</a>
			</Button>
		);
	}

	return (
		<div className="flex h-14 w-full items-stretch sm:w-auto">
			<Button
				asChild
				variant="ghost"
				className="h-auto flex-1 gap-2 rounded-l-lg rounded-r-none border border-r-0 border-neutral-200 bg-white px-5 text-base font-medium text-neutral-700 shadow-sm transition duration-150 active:scale-[0.99] hover:bg-neutral-50 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-200 dark:hover:bg-neutral-800"
			>
				<a href={primary.url}>
					<Download className="size-4 shrink-0" />
					Download for {os}
				</a>
			</Button>
			<DropdownMenu>
				<DropdownMenuTrigger asChild>
					<Button
						type="button"
						variant="ghost"
						aria-label="More download options"
						className="h-auto rounded-l-none rounded-r-lg border border-neutral-200 bg-white px-2.5 text-neutral-500 shadow-sm transition duration-150 hover:bg-neutral-50 dark:border-neutral-700 dark:bg-neutral-900 dark:text-neutral-400 dark:hover:bg-neutral-800"
					>
						<ChevronDown className="size-4" aria-hidden />
					</Button>
				</DropdownMenuTrigger>
				<DropdownMenuContent align="end" className="w-64">
					{alternatives.map((asset) => (
						<DropdownMenuItem key={asset.name} asChild>
							<a href={asset.url} className="cursor-pointer">
								<Download className="mr-2 size-3.5" />
								{getAssetLabel(asset.name)}
							</a>
						</DropdownMenuItem>
					))}
					<DropdownMenuItem asChild>
						<a
							href={fallbackUrl}
							target="_blank"
							rel="noopener noreferrer"
							className="cursor-pointer"
						>
							All downloads
						</a>
					</DropdownMenuItem>
				</DropdownMenuContent>
			</DropdownMenu>
		</div>
	);
}

const TabVideo = memo(function TabVideo({
	src,
	title,
	reduceMotion,
}: {
	src: string;
	title: string;
	reduceMotion: boolean;
}) {
	const videoRef = useRef<HTMLVideoElement>(null);
	const [hasLoaded, setHasLoaded] = useState(false);

	useEffect(() => {
		setHasLoaded(false);
		const video = videoRef.current;
		if (!video) return;
		video.currentTime = 0;
		// Respect reduced-motion: show the first frame and expose controls instead of autoplaying.
		if (!reduceMotion) {
			video.play().catch(() => {});
		}
	}, [reduceMotion]);

	const handleCanPlay = useCallback(() => {
		setHasLoaded(true);
	}, []);

	return (
		<div className="relative">
			<video
				ref={videoRef}
				key={src}
				src={src}
				preload={reduceMotion ? "metadata" : "auto"}
				aria-label={`${title} demo`}
				autoPlay={!reduceMotion}
				controls={reduceMotion}
				loop
				muted
				playsInline
				onCanPlay={handleCanPlay}
				className="aspect-video w-full rounded-lg sm:rounded-xl"
			/>
			{!hasLoaded && (
				<Skeleton className="absolute inset-0 aspect-video w-full rounded-lg bg-neutral-100 motion-reduce:animate-none sm:rounded-xl dark:bg-neutral-800" />
			)}
		</div>
	);
});

const UseCasePane = memo(function UseCasePane({
	useCase,
	reduceMotion,
}: {
	useCase: HeroUseCase;
	reduceMotion: boolean;
}) {
	const { expanded, open, close } = useExpandedMedia();
	const hasVideo = Boolean(useCase.src);

	const media = hasVideo ? (
		<Button
			type="button"
			variant="ghost"
			onClick={open}
			aria-label={`Expand ${useCase.title} demo`}
			className="h-auto w-full cursor-pointer rounded-none bg-neutral-50 p-2 hover:bg-neutral-50 sm:p-3 dark:bg-neutral-950 dark:hover:bg-neutral-950"
		>
			<TabVideo src={useCase.src as string} title={useCase.title} reduceMotion={reduceMotion} />
		</Button>
	) : (
		<div className="bg-neutral-50 p-2 sm:p-3 dark:bg-neutral-950">
			{useCase.demo && <HeroChatDemo demo={useCase.demo} reduceMotion={reduceMotion} />}
		</div>
	);

	const card = (
		<div className="relative overflow-hidden rounded-tl-xl rounded-tr-xl bg-white shadow-sm ring-1 shadow-black/10 ring-black/10 dark:bg-neutral-950">
			<div className="flex items-center gap-3 border-b border-neutral-200/60 px-4 py-3 sm:px-6 sm:py-4 dark:border-neutral-700/60">
				<div className="min-w-0">
					<h3 className="truncate text-base font-semibold text-neutral-900 sm:text-lg dark:text-white">
						{useCase.title}
					</h3>
					<p className="text-sm text-neutral-500 text-pretty dark:text-neutral-400">
						{useCase.description}
					</p>
				</div>
			</div>
			{media}
		</div>
	);

	return (
		<>
			{reduceMotion ? (
				card
			) : (
				<motion.div
					initial={{ opacity: 0, scale: 0.99, filter: "blur(10px)" }}
					animate={{ opacity: 1, scale: 1, filter: "blur(0px)" }}
					transition={{ duration: 0.3, ease: "easeOut" }}
					className="will-change-transform"
				>
					{card}
				</motion.div>
			)}

			<AnimatePresence>
				{expanded && hasVideo && (
					<ExpandedMediaOverlay
						src={useCase.src as string}
						alt={`${useCase.title} demo`}
						onClose={close}
					/>
				)}
			</AnimatePresence>
		</>
	);
});

const CategoryPanel = memo(function CategoryPanel({
	category,
	reduceMotion,
}: {
	category: HeroCategory;
	reduceMotion: boolean;
}) {
	return (
		<div className="flex w-full flex-col gap-3">
			<Tabs
				defaultValue={category.useCases[0]?.id}
				orientation="vertical"
				className="flex w-full flex-col gap-3 md:flex-row md:gap-4"
			>
				<ScrollArea className="w-full md:w-56 md:shrink-0">
					<TabsList className="flex h-auto w-max gap-1 bg-transparent p-0 md:w-full md:flex-col md:items-stretch">
						{category.useCases.map((useCase) => (
							<TabsTrigger
								key={useCase.id}
								value={useCase.id}
								className="h-auto shrink-0 touch-manipulation justify-start rounded-md px-3 py-2 text-left text-xs whitespace-normal data-[state=active]:bg-background data-[state=active]:shadow-sm sm:text-sm md:w-full"
							>
								{useCase.title}
							</TabsTrigger>
						))}
					</TabsList>
					<ScrollBar orientation="horizontal" className="md:hidden" />
				</ScrollArea>
				<div className="min-w-0 flex-1">
					{category.useCases.map((useCase) => (
						<TabsContent key={useCase.id} value={useCase.id} className="mt-0">
							<UseCasePane useCase={useCase} reduceMotion={reduceMotion} />
						</TabsContent>
					))}
				</div>
			</Tabs>
		</div>
	);
});
