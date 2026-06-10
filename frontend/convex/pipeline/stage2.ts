import {
  callLlm,
  parseJsonResponse,
} from "../lib/openrouter";
import { CLEANING_PLAN_PROMPT } from "../lib/prompts";
import { computeQualityMetrics } from "../lib/csv";

export async function runStage2(
  ctx: any,
  args: { data: Record<string, any>[]; schema: any }
) {
  const { data } = args;

  // Step 1: Deterministic quality profiling
  const qualityMetrics = computeQualityMetrics(data);

  // Step 2: LLM cleaning plan (if API key available)
  let cleaningPlan: any = {
    operations: [],
    description: "Rule-based cleaning plan",
    estimatedImpact: "Standard quality improvements",
  };

  const apiKey = process.env.OPENROUTER_API_KEY;
  if (apiKey) {
    try {
      const response = await callLlm(
        apiKey,
        CLEANING_PLAN_PROMPT,
        JSON.stringify(qualityMetrics, null, 2)
      );

      const llmResult = parseJsonResponse<{
        operations: Array<{
          column: string;
          issue: string;
          strategy: string;
          parameters: Record<string, any>;
          confidence: number;
          reasoning: string;
        }>;
        description: string;
        estimatedImpact: string;
      }>(response.content);

      if (llmResult.operations && llmResult.operations.length > 0) {
        cleaningPlan = llmResult;
      }
    } catch (e) {
      console.warn("LLM cleaning plan failed, using rule-based:", e);
    }
  }

  // Step 3: Apply basic cleaning operations
  let cleanedData = applyBasicCleaning(data, cleaningPlan.operations);

  return {
    qualityProfile: qualityMetrics,
    cleaningPlan,
    cleanedData,
    rowCountBefore: data.length,
    rowCountAfter: cleanedData.length,
  };
}

function applyBasicCleaning(
  data: Record<string, any>[],
  operations: any[]
): Record<string, any>[] {
  let result = [...data];
  const keys = Object.keys(result[0] || {});

  // ===== PII AUTO-MASKING (Enterprise Security) =====
  // Detect and mask personally identifiable information
  for (const key of keys) {
    const sampleVal = result.find((r) => typeof r[key] === "string")?.[key];
    if (typeof sampleVal === "string") {
      const piiType = detectPII(sampleVal);
      if (piiType) {
        result = result.map((row) => ({
          ...row,
          [key]: maskPII(String(row[key] || ""), piiType),
        }));
      }
    }
  }

  // Remove duplicate rows
  const seen = new Set<string>();
  result = result.filter((row) => {
    const key = JSON.stringify(Object.values(row));
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });

  // Impute missing values (simple mean/mode imputation)
  for (const key of keys) {
    const values = result.map((r) => r[key]);
    const nonNull = values.filter((v) => v !== null && v !== undefined && v !== "");

    if (nonNull.length === 0) continue;

    // Compute fill value
    const allNumbers = nonNull.every((v) => typeof v === "number");
    let fillValue: any;

    if (allNumbers) {
      fillValue = nonNull.reduce((s, v) => s + v, 0) / nonNull.length;
      fillValue = Math.round(fillValue * 100) / 100;
    } else {
      // Mode for categorical
      const freq = new Map<any, number>();
      for (const v of nonNull) {
        freq.set(v, (freq.get(v) || 0) + 1);
      }
      fillValue = [...freq.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] || "";
    }

    // Apply
    result = result.map((row) => ({
      ...row,
      [key]: row[key] === null || row[key] === undefined || row[key] === "" ? fillValue : row[key],
    }));
  }

  return result;
}

// ===== PII DETECTION =====
// Detects common PII patterns: Email, Phone, SSN, Credit Card
function detectPII(value: string): string | null {
  // Email addresses
  if (/^[\w.-]+@[\w.-]+\.\w+$/.test(value)) return "email";
  // Phone numbers (various formats)
  if (/^[\+]?[\d\s()-]{7,15}$/.test(value) && /\d{7,}/.test(value.replace(/[\s()-]/g, ""))) return "phone";
  // US SSN (XXX-XX-XXXX)
  if (/^\d{3}-\d{2}-\d{4}$/.test(value)) return "ssn";
  // Credit Card (16-digit with optional dashes/spaces)
  if (/^\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}$/.test(value)) return "credit_card";
  return null;
}

// ===== PII MASKING =====
// Masks detected PII while preserving partial info for analysis
function maskPII(value: string, type: string): string {
  switch (type) {
    case "email": {
      const [local, domain] = value.split("@");
      return `${local[0]}***@***${domain.slice(domain.indexOf("."))}`;
    }
    case "phone": {
      const digits = value.replace(/[\s()-]/g, "");
      const last4 = digits.slice(-4);
      return `*******${last4}`;
    }
    case "ssn": {
      return `***-**-${value.slice(-4)}`;
    }
    case "credit_card": {
      const digits = value.replace(/[\s-]/g, "");
      return `****-****-****-${digits.slice(-4)}`;
    }
    default:
      return value;
  }
}
