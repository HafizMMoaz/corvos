import { json, number, string, table } from "@rocicorp/zero";

/** JSON-compatible value; mirrors Zero's `ReadonlyJSONValue` (not exported from the package root). */
type FolderMetadataValue =
	| null
	| boolean
	| number
	| string
	| readonly FolderMetadataValue[]
	| { readonly [key: string]: FolderMetadataValue };

export type FolderMetadata = {
	readonly [key: string]: FolderMetadataValue;
};

export const folderTable = table("folders")
	.columns({
		id: number(),
		name: string(),
		position: string(),
		parentId: number().optional().from("parent_id"),
		workspaceId: number().from("workspace_id"),
		createdById: string().optional().from("created_by_id"),
		createdAt: number().from("created_at"),
		updatedAt: number().from("updated_at"),
		metadata: json<FolderMetadata>().optional().from("metadata"),
	})
	.primaryKey("id");
