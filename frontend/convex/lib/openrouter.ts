// OpenRouter API client for Convex Actions (PRIMARY LLM PROVIDER)
// Uses: qwen/qwen3-coder:free (primary), meta-llama/llama-4-maverick:free (fallback)
// Strict 2-tier OpenRouter fallback setup.

const OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1";
const DEFAULT_MODEL = "qwen/qwen3-coder:free";
const FALLBACK_MODEL = "meta-llama/llama-4-maverick:free";
const MAX_TOKENS = 4096;
const TEMPERATURE = 0.1;

export interface LlmResponse {
  content: string;
  model: string;
  usage?: { prompt_tokens: number; completion_tokens: number };
}

export async function callLlm(
  apiKey: string,
  systemPrompt: string,
  userPrompt: string,
  model: string = DEFAULT_MODEL,
  temperature: number = TEMPERATURE,
  appUrl: string = "http://localhost:3000"
): Promise<LlmResponse> {
  // 1st attempt: Primary OpenRouter model
  try {
    const response = await fetch(`${OPENROUTER_BASE_URL}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
        "HTTP-Referer": appUrl,
      },
      body: JSON.stringify({
        model,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt },
        ],
        temperature: temperature,
        max_tokens: MAX_TOKENS,
      }),
    });

    if (!response.ok) {
      throw new Error(`OpenRouter API error (${response.status})`);
    }

    const data = await response.json();
    return {
      content: data.choices[0]?.message?.content || "",
      model: data.model,
      usage: data.usage,
    };
  } catch (primaryError) {
    console.warn(`OpenRouter primary (${model}) failed:`, primaryError);
  }

  // 2nd attempt: Fallback OpenRouter model
  try {
    const fallbackModel = FALLBACK_MODEL;
    const response = await fetch(`${OPENROUTER_BASE_URL}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${apiKey}`,
        "HTTP-Referer": appUrl,
      },
      body: JSON.stringify({
        model: fallbackModel,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt },
        ],
        temperature: temperature,
        max_tokens: MAX_TOKENS,
      }),
    });

    if (!response.ok) {
      throw new Error(`OpenRouter API error (${response.status})`);
    }

    const data = await response.json();
    return {
      content: data.choices[0]?.message?.content || "",
      model: data.model,
      usage: data.usage,
    };
  } catch (fallbackError: any) {
    throw new Error(`OpenRouter primary and fallback models both failed: ${fallbackError.message || fallbackError}`);
  }
}

// Parse LLM response as JSON, stripping markdown code blocks if present
export function parseJsonResponse<T>(content: string): T {
  let cleaned = content.trim();
  if (cleaned.startsWith("```")) {
    const lines = cleaned.split("\n");
    if (lines[0].trim().startsWith("```")) lines.shift();
    if (lines.length > 0 && lines[lines.length - 1].trim() === "```") lines.pop();
    cleaned = lines.join("\n").trim();
  }
  return JSON.parse(cleaned) as T;
}
