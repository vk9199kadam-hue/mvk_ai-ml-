import { NextRequest } from "next/server";

export const runtime = "edge";

export async function POST(req: NextRequest) {
  try {
    const { editInstructions, currentContent } = await req.json();

    if (!editInstructions) {
      return new Response("Missing editInstructions", { status: 400 });
    }

    const apiKey = process.env.OPENROUTER_API_KEY;
    if (!apiKey) {
      return new Response("OPENROUTER_API_KEY is not configured", { status: 500 });
    }

    const systemPrompt = 
      "You are an expert technical editor. Edit the provided report section according to the user's instructions.\n" +
      "Maintain the same Markdown format and return ONLY the edited markdown text. Do not add conversational intro/outro text.";

    const userPrompt = 
      `Original Section Content:\n${currentContent}\n\nUser Instructions:\n${editInstructions}\n\nEdited Markdown:`;

    const openRouterResponse = await fetch("https://openrouter.ai/api/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${apiKey}`,
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "AutoInsight AI",
      },
      body: JSON.stringify({
        model: "qwen/qwen3-coder:free",
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userPrompt }
        ],
        stream: true,
      }),
    });

    if (!openRouterResponse.ok) {
      const errText = await openRouterResponse.text();
      return new Response(`OpenRouter error: ${errText}`, { status: openRouterResponse.status });
    }

    const encoder = new TextEncoder();
    const decoder = new TextDecoder();
    
    const stream = new ReadableStream({
      async start(controller) {
        const reader = openRouterResponse.body?.getReader();
        if (!reader) {
          controller.close();
          return;
        }

        let buffer = "";

        try {
          while (true) {
            const { done, value } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n");
            
            buffer = lines.pop() || "";

            for (const line of lines) {
              const cleaned = line.trim();
              if (!cleaned) continue;
              if (cleaned === "data: [DONE]") continue;

              if (cleaned.startsWith("data: ")) {
                try {
                  const jsonStr = cleaned.slice(6);
                  const parsed = JSON.parse(jsonStr);
                  const content = parsed.choices?.[0]?.delta?.content || "";
                  if (content) {
                    controller.enqueue(encoder.encode(content));
                  }
                } catch (jsonErr) {
                  // Partial line, ignore JSON parse error
                }
              }
            }
          }
          
          if (buffer && buffer.startsWith("data: ") && buffer !== "data: [DONE]") {
            try {
              const parsed = JSON.parse(buffer.slice(6));
              const content = parsed.choices?.[0]?.delta?.content || "";
              if (content) {
                controller.enqueue(encoder.encode(content));
              }
            } catch {}
          }
        } catch (streamErr) {
          controller.error(streamErr);
        } finally {
          controller.close();
        }
      }
    });

    return new Response(stream, {
      headers: {
        "Content-Type": "text/event-stream; charset=utf-8",
        "Cache-Control": "no-cache, no-transform",
        "Connection": "keep-alive",
      },
    });

  } catch (err: any) {
    return new Response(err?.message || "Internal server error", { status: 500 });
  }
}
