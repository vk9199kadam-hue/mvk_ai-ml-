import {
  callLlm,
  parseJsonResponse,
} from "../lib/openrouter";
import { LANGGRAPH_REASON_PROMPT } from "../lib/prompts";
import {
  getNumericColumns,
  computeCorrelationMatrix,
  computeUnivariateStats,
} from "../lib/csv";

export async function runStage3(
  ctx: any,
  args: { data: Record<string, any>[]; columns: string[]; schema: any }
) {
  const { data, columns } = args;

  // Step 1: Deterministic profiling
  const numericCols = getNumericColumns(data);
  const stats = computeUnivariateStats(data);
  const { matrix, candidates } = computeCorrelationMatrix(data);

  // Step 2: LLM relationship reasoning
  let relationships: any[] = [];
  let derivedColumns: any[] = [];

  const apiKey = process.env.OPENROUTER_API_KEY;
  if (apiKey) {
    try {
      const profileSummary = {
        columns: columns.map((c) => ({
          name: c,
          type: numericCols.includes(c) ? "numeric" : "categorical",
        })),
        numericColumnCount: numericCols.length,
        categoricalColumnCount: columns.length - numericCols.length,
        correlationCandidates: candidates.slice(0, 10).map((c) => ({
          source: c.sourceColumn,
          target: c.targetColumn,
          correlation: c.pearsonR,
        })),
      };

      const response = await callLlm(
        apiKey,
        LANGGRAPH_REASON_PROMPT,
        JSON.stringify(profileSummary, null, 2)
      );

      const llmResult = parseJsonResponse<{
        relationships: Array<{
          sourceColumn: string;
          targetColumn: string;
          relationshipType: string;
          confidence: number;
          description: string;
          chartHint: string;
        }>;
        derivedColumns: Array<{
          name: string;
          formula: string;
          dataType: string;
          description: string;
          confidence: number;
        }>;
      }>(response.content);

      if (llmResult.relationships) {
        relationships = llmResult.relationships.filter(
          (r) => r.confidence >= 0.65
        );
      }
      if (llmResult.derivedColumns) {
        derivedColumns = llmResult.derivedColumns;
      }
    } catch (e) {
      console.warn("LLM reasoning failed, using deterministic:", e);
    }
  }

  // Fallback: deterministic relationship candidates
  if (relationships.length === 0) {
    relationships = candidates.slice(0, 5).map((c) => ({
      sourceColumn: c.sourceColumn,
      targetColumn: c.targetColumn,
      relationshipType: Math.abs(c.pearsonR || 0) > 0.7 ? "one-to-one" : "one-to-many",
      confidence: Math.round(c.strength * 100) / 100,
      description: `${c.sourceColumn} correlates with ${c.targetColumn} (r=${c.pearsonR?.toFixed(3)})`,
      chartHint: Math.abs(c.pearsonR || 0) > 0.5 ? "scatter" : "bar",
    }));
  }

  // Generate derived column suggestions
  if (derivedColumns.length === 0 && numericCols.length >= 2) {
    for (let i = 0; i < numericCols.length - 1 && derivedColumns.length < 3; i++) {
      derivedColumns.push({
        name: `${numericCols[i]}_to_${numericCols[i + 1]}_ratio`,
        formula: `${numericCols[i]} / ${numericCols[i + 1]}`,
        dataType: "float",
        description: `Ratio of ${numericCols[i]} to ${numericCols[i + 1]}`,
        confidence: 0.7,
      });
    }
  }

  return { relationships, derivedColumns, correlationMatrix: matrix };
}
