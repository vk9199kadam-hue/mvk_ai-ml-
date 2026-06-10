// CSV parsing and data processing utilities for Convex Actions
// Simplified TypeScript replacements for Python's Polars/SciPy tools

export interface ColumnProfile {
  name: string;
  dtype: "number" | "string" | "boolean" | "date" | "unknown";
  nullCount: number;
  nullPercentage: number;
  cardinality: number;
  sampleValues: string[];
}

export interface SchemaProfile {
  columns: ColumnProfile[];
  rowCount: number;
  columnCount: number;
}

export interface UnivariateStats {
  [col: string]: {
    mean?: number;
    median?: number;
    std?: number;
    min?: number;
    max?: number;
    q1?: number;
    q3?: number;
    iqr?: number;
    nullCount: number;
    count: number;
  };
}

export interface CorrelationResult {
  [col1: string]: {
    [col2: string]: number;
  };
}

export interface RelationshipCandidate {
  sourceColumn: string;
  targetColumn: string;
  evidence: "correlation" | "value_overlap";
  strength: number;
  pearsonR?: number;
  overlapRatio?: number;
}

// Parse CSV text into array of row objects
export function parseCsvText(
  csvText: string,
  hasHeader: boolean = true
): Record<string, any>[] {
  const lines = csvText.split("\n").filter((l) => l.trim());
  if (lines.length === 0) return [];

  const headers = hasHeader
    ? lines[0].split(",").map((h) => h.trim().replace(/^"|"$/g, ""))
    : lines[0].split(",").map((_, i) => `col_${i}`);

  const dataLines = hasHeader ? lines.slice(1) : lines;
  const result: Record<string, any>[] = [];

  for (const line of dataLines) {
    const values = parseCsvLine(line);
    const row: Record<string, any> = {};
    headers.forEach((h, i) => {
      const val = values[i]?.trim().replace(/^"|"$/g, "") ?? null;
      // Try to parse as number
      const num = Number(val);
      row[h] = val === null || val === "" ? null : (isNaN(num) ? val : num);
    });
    result.push(row);
  }

  return result;
}

// Parse a single CSV line respecting quoted fields
function parseCsvLine(line: string): string[] {
  const result: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && i + 1 < line.length && line[i + 1] === '"') {
        current += '"';
        i++;
      } else {
        inQuotes = !inQuotes;
      }
    } else if (ch === "," && !inQuotes) {
      result.push(current);
      current = "";
    } else {
      current += ch;
    }
  }
  result.push(current);
  return result;
}

// Detect column types from parsed data
export function detectColumnTypes(
  data: Record<string, any>[]
): ColumnProfile[] {
  if (data.length === 0) return [];

  const columns: ColumnProfile[] = [];
  const keys = Object.keys(data[0]);

  for (const key of keys) {
    const values = data.map((r) => r[key]);
    const nonNull = values.filter((v) => v !== null && v !== undefined);
    const nullCount = values.length - nonNull.length;
    const uniqueVals = new Set(nonNull.map((v) => String(v)));

    // Detect type
    let dtype: ColumnProfile["dtype"] = "unknown";
    const sampleStr = nonNull.length > 0 ? String(nonNull[0]) : "";

    if (nonNull.length > 0) {
      const allNumbers = nonNull.every((v) => typeof v === "number");
      const allBooleans = nonNull.every(
        (v) => v === true || v === false || v === "true" || v === "false"
      );
      const dateMatch = /^\d{4}-\d{2}-\d{2}/.test(sampleStr);

      if (allBooleans && uniqueVals.size <= 2) {
        dtype = "boolean";
      } else if (allNumbers) {
        dtype = "number";
      } else if (dateMatch) {
        dtype = "date";
      } else {
        dtype = "string";
      }
    }

    columns.push({
      name: key,
      dtype,
      nullCount,
      nullPercentage: Math.round((nullCount / values.length) * 10000) / 100,
      cardinality: uniqueVals.size,
      sampleValues: Array.from(uniqueVals).slice(0, 5),
    });
  }

  return columns;
}

// Get numeric columns from parsed data
export function getNumericColumns(
  data: Record<string, any>[]
): string[] {
  if (data.length === 0) return [];
  const keys = Object.keys(data[0]);
  return keys.filter((key) => {
    const nonNull = data
      .map((r) => r[key])
      .filter((v) => v !== null && v !== undefined);
    return nonNull.length > 0 && nonNull.every((v) => typeof v === "number");
  });
}

// Compute univariate statistics for numeric columns
export function computeUnivariateStats(
  data: Record<string, any>[]
): UnivariateStats {
  const numericCols = getNumericColumns(data);
  const stats: UnivariateStats = {};

  for (const col of numericCols) {
    const values = data
      .map((r) => r[col])
      .filter((v): v is number => v !== null && v !== undefined && typeof v === "number");

    if (values.length === 0) continue;

    values.sort((a, b) => a - b);
    const n = values.length;
    const mean = values.reduce((s, v) => s + v, 0) / n;
    const variance =
      values.reduce((s, v) => s + (v - mean) ** 2, 0) / (n - 1 || 1);
    const std = Math.sqrt(variance);
    const min = values[0];
    const max = values[n - 1];
    const median =
      n % 2 === 0
        ? (values[n / 2 - 1] + values[n / 2]) / 2
        : values[Math.floor(n / 2)];
    const q1 = values[Math.floor(n * 0.25)];
    const q3 = values[Math.floor(n * 0.75)];

    stats[col] = {
      mean: Math.round(mean * 10000) / 10000,
      median: Math.round(median * 10000) / 10000,
      std: Math.round(std * 10000) / 10000,
      min: Math.round(min * 10000) / 10000,
      max: Math.round(max * 10000) / 10000,
      q1: Math.round(q1 * 10000) / 10000,
      q3: Math.round(q3 * 10000) / 10000,
      iqr: Math.round((q3 - q1) * 10000) / 10000,
      nullCount: data.filter((r) => r[col] === null || r[col] === undefined).length,
      count: values.length,
    };
  }

  return stats;
}

// Compute Pearson correlation between two numeric arrays
function pearsonCorrelation(x: number[], y: number[]): number {
  const n = Math.min(x.length, y.length);
  if (n < 3) return 0;

  const meanX = x.reduce((s, v) => s + v, 0) / n;
  const meanY = y.reduce((s, v) => s + v, 0) / n;

  let num = 0;
  let denX = 0;
  let denY = 0;

  for (let i = 0; i < n; i++) {
    const dx = x[i] - meanX;
    const dy = y[i] - meanY;
    num += dx * dy;
    denX += dx * dx;
    denY += dy * dy;
  }

  const den = Math.sqrt(denX * denY);
  return den === 0 ? 0 : Math.round((num / den) * 10000) / 10000;
}

// Compute correlation matrix for numeric columns
export function computeCorrelationMatrix(
  data: Record<string, any>[]
): { matrix: CorrelationResult; candidates: RelationshipCandidate[] } {
  const numericCols = getNumericColumns(data);
  const matrix: CorrelationResult = {};
  const candidates: RelationshipCandidate[] = [];

  for (let i = 0; i < numericCols.length; i++) {
    const col1 = numericCols[i];
    matrix[col1] = {};

    for (let j = 0; j < numericCols.length; j++) {
      const col2 = numericCols[j];

      if (i === j) {
        matrix[col1][col2] = 1;
        continue;
      }

      // Get paired non-null values
      const pairs = data
        .map((r) => ({ x: r[col1], y: r[col2] }))
        .filter(
          (p) =>
            p.x !== null && p.x !== undefined &&
            p.y !== null && p.y !== undefined
        );

      const r =
        pairs.length >= 3
          ? pearsonCorrelation(
              pairs.map((p) => p.x),
              pairs.map((p) => p.y)
            )
          : 0;

      matrix[col1][col2] = r;

      // Add as candidate if |r| > 0.5
      if (Math.abs(r) >= 0.5 && col1 < col2) {
        candidates.push({
          sourceColumn: col1,
          targetColumn: col2,
          evidence: "correlation",
          strength: Math.abs(r),
          pearsonR: r,
        });
      }
    }
  }

  return { matrix, candidates };
}

// Detect missing values and return a quality profile
export interface QualityMetrics {
  totalCells: number;
  totalMissing: number;
  missingPercentage: number;
  columnsWithMissing: { column: string; nullCount: number; nullPct: number }[];
  duplicateRows: number;
  qualityScore: number;
}

export function computeQualityMetrics(
  data: Record<string, any>[]
): QualityMetrics {
  if (data.length === 0) {
    return { totalCells: 0, totalMissing: 0, missingPercentage: 0, columnsWithMissing: [], duplicateRows: 0, qualityScore: 1 };
  }

  const keys = Object.keys(data[0]);
  const totalCells = data.length * keys.length;
  let totalMissing = 0;
  const columnsWithMissing: QualityMetrics["columnsWithMissing"] = [];

  for (const key of keys) {
    const nullCount = data.filter(
      (r) => r[key] === null || r[key] === undefined || r[key] === ""
    ).length;
    totalMissing += nullCount;
    if (nullCount > 0) {
      columnsWithMissing.push({
        column: key,
        nullCount,
        nullPct: Math.round((nullCount / data.length) * 10000) / 100,
      });
    }
  }

  // Detect duplicate rows
  const seen = new Set<string>();
  let duplicateRows = 0;
  for (const row of data) {
    const key = JSON.stringify(Object.values(row));
    if (seen.has(key)) duplicateRows++;
    else seen.add(key);
  }

  const missingPct = Math.round((totalMissing / totalCells) * 10000) / 100;
  const qualityScore = Math.max(0, Math.round((1 - missingPct / 100 - duplicateRows / data.length * 0.1) * 10000) / 10000);

  return {
    totalCells,
    totalMissing,
    missingPercentage: missingPct,
    columnsWithMissing,
    duplicateRows,
    qualityScore,
  };
}

// Sample data for LLM inference (first N rows as formatted text)
export function sampleDataForLLM(
  data: Record<string, any>[],
  maxRows: number = 20
): string {
  const sample = data.slice(0, maxRows);
  if (sample.length === 0) return "";
  const keys = Object.keys(sample[0]);

  const lines: string[] = [];
  lines.push(keys.join(" | "));
  lines.push("-".repeat(keys.join(" | ").length));

  for (const row of sample) {
    const values = keys.map((k) => String(row[k] ?? "").slice(0, 50));
    lines.push(values.join(" | "));
  }

  return lines.join("\n");
}

// Get unique values count for columns
export function getCardinality(
  data: Record<string, any>[],
  columns: string[]
): Record<string, number> {
  const result: Record<string, number> = {};
  for (const col of columns) {
    const vals = new Set(data.map((r) => r[col]).filter((v) => v !== null));
    result[col] = vals.size;
  }
  return result;
}
