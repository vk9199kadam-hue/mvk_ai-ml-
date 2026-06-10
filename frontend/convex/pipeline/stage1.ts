import {
  callLlm,
  parseJsonResponse,
} from "../lib/openrouter";
import { SCHEMA_INFERENCE_PROMPT } from "../lib/prompts";
import {
  detectColumnTypes,
} from "../lib/csv";

export async function runStage1(
  ctx: any,
  args: { data: Record<string, any>[]; allColumns: string[] }
) {
  const { data, allColumns } = args;

  // Step 1: Deterministic column type detection
  const columns = detectColumnTypes(data);

  // Step 2: Try LLM inference for enhanced schema
  // Uses OPENROUTER_API_KEY (OpenRouter is the sole LLM provider)
  const apiKey = process.env.OPENROUTER_API_KEY;
  if (apiKey) {
    try {
      const sampleText = JSON.stringify(data.slice(0, 20), null, 2);
      const columnList = allColumns.join(", ");

      const response = await callLlm(
        apiKey,
        SCHEMA_INFERENCE_PROMPT,
        `Columns: ${columnList}\n\nSample Data:\n${sampleText}`
      );

      const llmResult = parseJsonResponse<{
        columns: Array<{
          columnName: string;
          detectedType: string;
          confidence: number;
          reasoning: string;
          nullable: boolean;
          sampleValues: string[];
        }>;
        overallConfidence: number;
        rowCount: number;
      }>(response.content);

      // Merge LLM results with deterministic detection
      if (llmResult.columns && llmResult.columns.length > 0) {
        const llmMap = new Map(
          llmResult.columns.map((c) => [c.columnName, c])
        );

        for (const col of columns) {
          const llmCol = llmMap.get(col.name);
          if (llmCol && llmCol.confidence >= 0.7) {
            col.dtype = mapLLMType(llmCol.detectedType);
          }
        }

        return {
          columns,
          overallConfidence: llmResult.overallConfidence || 0.8,
          rowCount: data.length,
          llmEnhanced: true,
        };
      }
    } catch (e) {
      console.warn("LLM schema inference failed, using deterministic:", e);
    }
  }

  // Fallback: purely deterministic
  return {
    columns,
    overallConfidence: 0.75,
    rowCount: data.length,
    llmEnhanced: false,
  };
}

function mapLLMType(type: string): "number" | "string" | "boolean" | "date" | "unknown" {
  const lower = type.toLowerCase();
  if (lower.includes("int") || lower.includes("float") || lower === "number") return "number";
  if (lower === "boolean") return "boolean";
  if (lower.includes("date")) return "date";
  if (lower === "str" || lower === "string" || lower === "text" || lower === "categorical") return "string";
  return "unknown";
}
