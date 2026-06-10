import { v } from "convex/values";
import { action } from "./_generated/server";
import { api, internal as internalRaw } from "./_generated/api";
const internal = internalRaw as any;

export const discoverCrossRelations = action({
  args: {
    userId: v.id("users"),
  },
  handler: async (ctx, args) => {
    // 1. Get all uploads for this user
    const uploads = await ctx.runQuery(api.uploads.listUploads, {
      userId: args.userId,
    });
    if (!uploads || uploads.length < 2) {
      return { success: false, message: "Upload at least two datasets to find relationships" };
    }

    // 2. Load the dataset headers
    const datasetsInfo: Array<{
      uploadId: string;
      fileName: string;
      columns: string[];
    }> = [];

    for (const u of uploads) {
      const dataset = await ctx.runQuery(internal.datasets.getDatasetByUpload, {
        uploadId: u._id,
      });
      if (dataset && dataset.columns) {
        datasetsInfo.push({
          uploadId: u._id,
          fileName: u.fileName,
          columns: dataset.columns,
        });
      }
    }

    const suggestions: any[] = [];
    const idKeys = ["id", "uid", "code", "key"];

    // 3. Scan pairs of datasets for matching column names
    for (let i = 0; i < datasetsInfo.length; i++) {
      for (let j = i + 1; j < datasetsInfo.length; j++) {
        const d1 = datasetsInfo[i];
        const d2 = datasetsInfo[j];

        for (const col1 of d1.columns) {
          for (const col2 of d2.columns) {
            const clean1 = col1.toLowerCase().replace(/[^a-z0-9]/g, "");
            const clean2 = col2.toLowerCase().replace(/[^a-z0-9]/g, "");

            // If columns match or contain standard join keys (like customer_id matching id)
            const isMatch = 
              clean1 === clean2 || 
              (clean1.endsWith("id") && clean2 === "id" && clean1.startsWith(clean2)) ||
              (clean2.endsWith("id") && clean1 === "id" && clean2.startsWith(clean1));

            if (isMatch) {
              // Exclude generic match like id=id if they are both the primary key of different entities
              if (clean1 === "id" && clean2 === "id") continue;

              // Check if relation already exists in datasetRelations
              const existing = await ctx.runQuery(api.joins.listRelations, {
                userId: args.userId,
              });

              const alreadyExists = existing.some((r: any) => 
                (r.sourceUploadId === d1.uploadId && r.targetUploadId === d2.uploadId && r.sourceColumn === col1 && r.targetColumn === col2) ||
                (r.sourceUploadId === d2.uploadId && r.targetUploadId === d1.uploadId && r.sourceColumn === col2 && r.targetColumn === col1)
              );

              if (!alreadyExists) {
                // Auto create relation as a suggestion
                const name = `${d1.fileName.replace(".csv", "")} 🔗 ${d2.fileName.replace(".csv", "")} (${col1})`;
                const relationId = await ctx.runMutation(api.joins.createRelation, {
                  userId: args.userId,
                  name,
                  description: `Automatically suggested relationship matching ${col1} in ${d1.fileName} with ${col2} in ${d2.fileName}`,
                  sourceUploadId: d1.uploadId as any,
                  targetUploadId: d2.uploadId as any,
                  sourceColumn: col1,
                  targetColumn: col2,
                  joinType: "inner",
                });

                suggestions.push({
                  relationId,
                  name,
                  source: d1.fileName,
                  target: d2.fileName,
                  sourceColumn: col1,
                  targetColumn: col2,
                });
              }
            }
          }
        }
      }
    }

    return {
      success: true,
      found: suggestions.length,
      suggestions,
    };
  },
});
