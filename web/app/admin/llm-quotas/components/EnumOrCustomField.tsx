"use client";

import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";

const CUSTOM_OPTION = "__custom__";

/**
 * A Select for a known value set (e.g. `Transport`/`AuthStyle` from
 * `backend/app/services/provider_registry.py`) that falls back to a free-text
 * input for anything else -- the backend stores these fields as plain
 * strings with no server-side enum constraint, so an admin-entered custom
 * value has to stay representable.
 */
export function EnumOrCustomField({
	id,
	options,
	value,
	onChange,
	disabled,
	placeholder,
}: {
	id: string;
	options: readonly string[];
	value: string;
	onChange: (value: string) => void;
	disabled?: boolean;
	placeholder: string;
}) {
	const [isCustom, setIsCustom] = useState(value !== "" && !options.includes(value));

	useEffect(() => {
		setIsCustom(value !== "" && !options.includes(value));
	}, [value, options]);

	return (
		<div className="space-y-2">
			<Select
				value={isCustom ? CUSTOM_OPTION : value}
				onValueChange={(next) => {
					if (next === CUSTOM_OPTION) {
						setIsCustom(true);
						onChange("");
					} else {
						setIsCustom(false);
						onChange(next);
					}
				}}
				disabled={disabled}
			>
				<SelectTrigger id={id} className="w-full">
					<SelectValue placeholder={placeholder} />
				</SelectTrigger>
				<SelectContent>
					{options.map((option) => (
						<SelectItem key={option} value={option}>
							{option}
						</SelectItem>
					))}
					<SelectItem value={CUSTOM_OPTION}>Custom...</SelectItem>
				</SelectContent>
			</Select>
			{isCustom && (
				<Input
					value={value}
					onChange={(event) => onChange(event.target.value)}
					placeholder="Enter a custom value"
					disabled={disabled}
				/>
			)}
		</div>
	);
}
