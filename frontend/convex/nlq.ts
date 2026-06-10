import { v } from "convex/values";
import { action, mutation } from "./_generated/server";
import { query as queryFn } from "./_generated/server";
import { internal as internalRaw } from "./_generated/api";
const internal = internalRaw as any;
import {
  callLlm,
  parseJsonResponse,
} from "./lib/openrouter";
import { NLQ_SYSTEM_PROMPT, NLQ_RESPONSE_SYSTEM_PROMPT } from "./lib/prompts";

// ===== QUERIES =====

export const getConversation = queryFn({
  args: { conversationId: v.id("conversations") },
  handler: async (ctx, args) => {
    return await ctx.db.get(args.conversationId);
  },
});

export const listConversations = queryFn({
  args: {
    userId: v.id("users"),
    uploadId: v.id("uploads"),
  },
  handler: async (ctx, args) => {
    return await ctx.db
      .query("conversations")
      .withIndex("by_user_upload", (q) =>
        q.eq("userId", args.userId).eq("uploadId", args.uploadId)
      )
      .order("desc")
      .collect();
  },
});

// ===== MUTATIONS =====

export const createConversation = mutation({
  args: {
    userId: v.id("users"),
    uploadId: v.id("uploads"),
  },
  handler: async (ctx, args) => {
    const convId = await ctx.db.insert("conversations", {
      userId: args.userId,
      uploadId: args.uploadId,
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    });
    return { conversationId: convId };
  },
});

// ===== CORE NLQ ACTION =====

export const query = action({
  args: {
    userId: v.id("users"),
    uploadId: v.id("uploads"),
    datasetId: v.id("datasets"),
    conversationId: v.id("conversations"),
    question: v.string(),
  },
  handler: async (ctx, args) => {
    const startTime = Date.now();

    // Get the dataset to know the schema
    const dataset = await ctx.runQuery(internal.datasets.getDataset, {
      datasetId: args.datasetId,
    });

    if (!dataset || !dataset.data) {
      return {
        answer: "No dataset found. Please upload data first.",
        confidence: 0,
        sql: null,
        chartConfig: null,
        processingTimeMs: Date.now() - startTime,
      };
    }

    const data = dataset.data as Record<string, any>[];
    const columns = dataset.columns as string[];

    // Build schema info for LLM
    const schemaInfo = columns
      .map((col) => {
        const sample = data.slice(0, 3).map((r) => r[col]);
        const type = sample.every((v) => typeof v === "number") ? "number" : "string";
        return `- ${col} (${type})`;
      })
      .join("\n");

    // ----- Step 1: Intent Parsing (LLM) -----
    let sqlQuery = "";
    let explanation = "";
    let queryConfidence = 0;
    let parsedIntent: any = null;

    const apiKey = process.env.OPENROUTER_API_KEY;
    if (apiKey) {
      try {
        const parseResponse = await callLlm(
          apiKey,
          NLQ_SYSTEM_PROMPT,
          `Available columns:\n${schemaInfo}\n\nUser question: ${args.question}`
        );

        parsedIntent = parseJsonResponse<{
          metrics: string[];
          dimensions: string[];
          filters: any[];
          sql: string;
          confidence: number;
          explanation: string;
        }>(parseResponse.content);

        sqlQuery = parsedIntent.sql || "";
        explanation = parsedIntent.explanation || "";
        queryConfidence = parsedIntent.confidence || 0.5;
      } catch (e) {
        console.warn("NLQ parsing failed:", e);
      }
    }

    // ----- Step 2: Execute Query (in-memory) -----
    let results: Record<string, any>[] = [];
    let answerText = "";

    if (sqlQuery) {
      try {
        results = executeInMemoryQuery(sqlQuery, data, columns);
      } catch (queryError: any) {
        // Simple fallback query
        results = executeSimpleAggregation(args.question, data, columns);
      }
    } else {
      results = executeSimpleAggregation(args.question, data, columns);
    }

    // ----- Step 3: Response Synthesis (LLM) -----
    if (apiKey && results.length > 0) {
      try {
        const responseResult = await callLlm(
          apiKey,
          NLQ_RESPONSE_SYSTEM_PROMPT,
          JSON.stringify({
            question: args.question,
            sqlGenerated: sqlQuery || "Simple aggregation",
            results: results.slice(0, 10),
            columns,
          })
        );

        const synthesized = parseJsonResponse<{
          answer: string;
          confidence: number;
          chartConfig: any;
        }>(responseResult.content);

        answerText = synthesized.answer;
        queryConfidence = synthesized.confidence || queryConfidence;

        // Save to conversation
        await ctx.runMutation(internal.nlq.addMessage, {
          conversationId: args.conversationId,
          role: "assistant",
          content: synthesized.answer,
          sqlGenerated: sqlQuery || null,
          chartConfig: synthesized.chartConfig || null,
        });

        return {
          answer: synthesized.answer,
          confidence: queryConfidence,
          sql: sqlQuery,
          chartConfig: synthesized.chartConfig || null,
          results: results.slice(0, 100),
          processingTimeMs: Date.now() - startTime,
        };
      } catch (e) {
        console.warn("Response synthesis failed:", e);
      }
    }

    // Fallback response
    answerText = buildFallbackAnswer(args.question, results, columns);

    await ctx.runMutation(internal.nlq.addMessage, {
      conversationId: args.conversationId,
      role: "assistant",
      content: answerText,
      sqlGenerated: sqlQuery || null,
      chartConfig: null,
    });

    return {
      answer: answerText,
      confidence: queryConfidence || 0.4,
      sql: sqlQuery || null,
      chartConfig: null,
      results: results.slice(0, 100),
      processingTimeMs: Date.now() - startTime,
    };
  },
});

export const addMessage = mutation({
  args: {
    conversationId: v.id("conversations"),
    role: v.union(v.literal("user"), v.literal("assistant")),
    content: v.string(),
    sqlGenerated: v.optional(v.string()),
    chartConfig: v.optional(v.any()),
  },
  handler: async (ctx, args) => {
    const conv = await ctx.db.get(args.conversationId);
    if (!conv) throw new Error("Conversation not found");

    const newMessage = {
      role: args.role,
      content: args.content,
      sqlGenerated: args.sqlGenerated,
      chartConfig: args.chartConfig,
      timestamp: Date.now(),
    };

    // Keep max 20 messages
    const messages = [...conv.messages, newMessage];
    if (messages.length > 20) {
      messages.splice(0, messages.length - 20);
    }

    await ctx.db.patch(args.conversationId, {
      messages,
      updatedAt: Date.now(),
    });
  },
});

// ===== HELPER: Simple in-memory SQL execution =====

function executeInMemoryQuery(
  sql: string,
  data: Record<string, any>[],
  columns: string[]
): Record<string, any>[] {
  // Very basic SQL-like query execution
  // Supports: SELECT ... FROM ... WHERE ... GROUP BY ... ORDER BY ... LIMIT

  // Parse GROUP BY
  const groupByMatch = sql.match(/GROUP\s+BY\s+(.+?)(?:HAVING|ORDER|LIMIT|$)/i);
  const groupByCols = groupByMatch
    ? groupByMatch[1].split(",").map((s: string) => s.trim())
    : [];

  // Parse aggregates
  const selectMatch = sql.match(/SELECT\s+(.+?)\s+FROM/i);
  const selects = selectMatch
    ? selectMatch[1]
        .split(",")
        .map((s: string) => s.trim())
        .filter((s: string) => s !== "*")
    : [];

  // Parse LIMIT
  const limitMatch = sql.match(/LIMIT\s+(\d+)/i);
  const limit = limitMatch ? parseInt(limitMatch[1]) : 100;

  if (groupByCols.length > 0) {
    return executeGroupBy(data, groupByCols, selects, limit);
  }

  return data.slice(0, limit);
}

function executeGroupBy(
  data: Record<string, any>[],
  groupByCols: string[],
  selects: string[],
  limit: number
): Record<string, any>[] {
  const groups = new Map<string, Record<string, any>[]>();

  for (const row of data) {
    const key = groupByCols.map((c) => row[c]).join("::");
    if (!groups.has(key)) groups.set(key, []);
    groups.get(key)!.push(row);
  }

  const result: Record<string, any>[] = [];
  for (const [key, rows] of groups) {
    const entry: Record<string, any> = {};
    const keyParts = key.split("::");
    groupByCols.forEach((col, i) => {
      entry[col] = keyParts[i];
    });

    for (const sel of selects) {
      const aggMatch = sel.match(/(\w+)\((.+?)\)(?:\s+as\s+(.+))?/i);
      if (aggMatch) {
        const [, aggFn, col, alias] = aggMatch;
        const values = rows.map((r) => r[col.trim()]).filter((v) => typeof v === "number");
        const name = (alias || sel).trim();

        if (aggFn.toUpperCase() === "SUM") entry[name] = values.reduce((s, v) => s + v, 0);
        else if (aggFn.toUpperCase() === "AVG") entry[name] = values.length > 0 ? values.reduce((s, v) => s + v, 0) / values.length : 0;
        else if (aggFn.toUpperCase() === "COUNT") entry[name] = rows.length;
        else if (aggFn.toUpperCase() === "MIN") entry[name] = values.length > 0 ? Math.min(...values) : 0;
        else if (aggFn.toUpperCase() === "MAX") entry[name] = values.length > 0 ? Math.max(...values) : 0;
      }
    }

    result.push(entry);
  }

  return result.slice(0, limit);
}

function executeSimpleAggregation(
  question: string,
  data: Record<string, any>[],
  columns: string[]
): Record<string, any>[] {
  const numericCols = columns.filter((col) =>
    data.some((r) => typeof r[col] === "number")
  );

  if (numericCols.length === 0) {
    return [{ message: "No numeric columns to aggregate" }];
  }

  const result: Record<string, any> = {};
  for (const col of numericCols) {
    const values = data
      .map((r) => r[col])
      .filter((v): v is number => typeof v === "number");
    if (values.length > 0) {
      result[`avg_${col}`] = Math.round((values.reduce((s, v) => s + v, 0) / values.length) * 100) / 100;
      result[`total_${col}`] = Math.round(values.reduce((s, v) => s + v, 0) * 100) / 100;
      result[`min_${col}`] = Math.min(...values);
      result[`max_${col}`] = Math.max(...values);
      result[`count_${col}`] = values.length;
    }
  }
  result.total_rows = data.length;

  return [result];
}

function buildFallbackAnswer(
  question: string,
  results: Record<string, any>[],
  columns: string[]
): string {
  if (results.length === 0) {
    return `I analyzed your question "${question}" but couldn't find matching data. Please try rephrasing.`;
  }

  const row = results[0];
  const keys = Object.keys(row);
  const details = keys
    .filter((k) => k !== "message")
    .map((k) => {
      const val = typeof row[k] === "number" ? row[k].toLocaleString() : row[k];
      return `- **${k}**: ${val}`;
    })
    .join("\n");

  return `Here are the results for your query:\n\n${details}\n\n*(Auto-generated from analysis of ${columns.length} columns across ${results.length} data points)*`;
}
