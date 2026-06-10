"use client";

import React, { useState, useRef, useEffect } from "react";
import Layout from "@/components/Layout";
import { useAction, useMutation, useQuery } from "convex/react";
import { api } from "../../../convex/_generated/api";
import { generateId, cn } from "@/lib/utils";
import { useNlqStore } from "@/store";
import ChartWidget, { createChartData } from "@/components/ChartWidget";
import type { Id } from "../../../convex/_generated/dataModel";
import toast from "react-hot-toast";

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  confidence?: number;
  chart_config?: any;
}

// ── Chat Message Component ───────────────────────────────────────────────

function ChatBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div className={cn("flex gap-3 animate-slide-up", isUser ? "justify-end" : "justify-start")}>
      {!isUser && (
        <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-purple-600 rounded-full flex items-center justify-center flex-shrink-0 mt-1">
          <span className="text-white text-xs font-bold">AI</span>
        </div>
      )}
      <div
        className={cn(
          "max-w-[75%] rounded-2xl px-4 py-3",
          isUser
            ? "bg-blue-600 text-white rounded-br-sm"
            : "bg-gray-100 text-gray-900 rounded-bl-sm"
        )}
      >
        <p className="text-sm leading-relaxed whitespace-pre-wrap">{message.content}</p>
        {message.confidence !== undefined && !isUser && (
          <div className="flex items-center gap-2 mt-2 pt-2 border-t border-gray-200">
            <span
              className={cn(
                "text-xs font-medium",
                message.confidence >= 0.9
                  ? "text-green-600"
                  : message.confidence >= 0.7
                  ? "text-yellow-600"
                  : "text-orange-600"
              )}
            >
              Confidence: {Math.round(message.confidence * 100)}%
            </span>
          </div>
        )}
        <span className="text-xs text-gray-400 mt-1 block">
          {new Date(message.timestamp).toLocaleTimeString()}
        </span>
      </div>
      {isUser && (
        <div className="w-8 h-8 bg-gray-200 rounded-full flex items-center justify-center flex-shrink-0 mt-1">
          <span className="text-gray-600 text-xs font-bold">U</span>
        </div>
      )}
    </div>
  );
}

// ── Suggested Questions ──────────────────────────────────────────────────

const SUGGESTED_QUESTIONS = [
  "What are the key trends in this dataset?",
  "Show me the correlation between age and salary",
  "Which columns have the most missing values?",
  "What insights can you extract from this data?",
  "Create a summary dashboard layout",
  "Are there any anomalies I should investigate?",
];

// ── NLQ Chat Page ────────────────────────────────────────────────────────

export default function NLQChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "👋 Welcome to AutoInsight AI!\n\nI can help you explore and analyze your data using natural language. Try asking about trends, correlations, or request a dashboard layout.\n\n**Sample questions:**\n- *\"What are the key trends in this dataset?\"*\n- *\"Show me the correlation between age and salary\"*\n- *\"Create a dashboard layout\"*",
      timestamp: new Date().toISOString(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [selectedUploadId, setSelectedUploadId] = useState<string>("");
  const [conversationId, setConversationId] = useState<string | undefined>(undefined);
  const [chartData, setChartData] = useState<Record<string, any>[] | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { showReasoning, toggleReasoning } = useNlqStore();

  // Load user info
  const [storedUser] = useState(() => {
    if (typeof window !== "undefined") {
      const u = localStorage.getItem("user");
      return u ? JSON.parse(u) : null;
    }
    return null;
  });
  const userId = storedUser?._id as Id<"users"> | undefined;

  // Load user uploads
  const uploads = useQuery(api.uploads.listUploads, userId ? { userId } : "skip");
  const uploadList = (uploads || []) as Array<{ _id: string; fileName: string; status: string }>;
  const completedUploads = uploadList.filter((u) => u.status === "completed");

  // Automatically select first completed upload if none is selected
  useEffect(() => {
    if (!selectedUploadId && completedUploads.length > 0) {
      setSelectedUploadId(completedUploads[0]._id);
    }
  }, [completedUploads, selectedUploadId]);

  // Load dataset for the selected upload ID
  const dataset = useQuery(
    api.datasets.getDatasetByUpload,
    selectedUploadId ? { uploadId: selectedUploadId as Id<"uploads"> } : "skip"
  );

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Convex action for NLQ queries
  const nlqQuery = useAction(api.nlq.query);
  const createConversation = useMutation(api.nlq.createConversation);

  const handleSend = async () => {
    const question = input.trim();
    if (!question || isLoading) return;

    if (!userId) {
      toast.error("You must be logged in");
      return;
    }

    if (!selectedUploadId) {
      toast.error("Please upload or select a dataset first");
      return;
    }

    if (!dataset?._id) {
      toast.error("Dataset loading. Please wait...");
      return;
    }

    setInput("");
    setIsLoading(true);

    // Add user message
    const userMessage = {
      id: generateId(), role: "user" as const, content: question, timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMessage]);

    try {
      // Create conversation if first message
      let convId = conversationId;
      if (!convId) {
        const { conversationId: newConvId } = await createConversation({
          userId: userId,
          uploadId: selectedUploadId as Id<"uploads">,
        });
        convId = newConvId;
        setConversationId(convId);
      }

      // Call Convex NLQ action
      const response = await nlqQuery({
        userId: userId,
        uploadId: selectedUploadId as Id<"uploads">,
        datasetId: dataset._id,
        conversationId: convId as any,
        question,
      });

      // Set chart data if response has chart config
      if (response.chartConfig) {
        setChartData([response.chartConfig as any]);
      }

      const assistantMessage = {
        id: generateId(),
        role: "assistant" as const,
        content: response.answer || "I processed your query.",
        timestamp: new Date().toISOString(),
        confidence: response.confidence,
        chart_config: response.chartConfig || undefined,
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err: any) {
      toast.error(err?.message || "Query failed");
      setMessages((prev) => [...prev, {
        id: generateId(), role: "assistant" as const,
        content: "I'm sorry, I couldn't process that query. Please try again.",
        timestamp: new Date().toISOString(), confidence: 0,
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleSuggestedQuestion = (question: string) => {
    setInput(question);
  };

  return (
    <Layout>
      <div className="max-w-4xl mx-auto h-[calc(100vh-8rem)] flex flex-col animate-fade-in">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">NLQ Chat</h1>
            <p className="text-sm text-gray-500 mt-1">
              Ask questions about your data in natural language
            </p>
          </div>
          <select
            value={selectedUploadId}
            onChange={(e) => {
              setSelectedUploadId(e.target.value);
              setConversationId(undefined);
              setMessages([
                {
                  id: "welcome",
                  role: "assistant",
                  content: "👋 Welcome to AutoInsight AI!\n\nI can help you explore and analyze your data using natural language. Try asking about trends, correlations, or request a dashboard layout.\n\n**Sample questions:**\n- *\"What are the key trends in this dataset?\"*\n- *\"Show me the correlation between age and salary\"*\n- *\"Create a dashboard layout\"*",
                  timestamp: new Date().toISOString(),
                },
              ]);
              setChartData(null);
            }}
            className="input-field w-64"
          >
            <option value="">Select a dataset...</option>
            {completedUploads.map((u) => (
              <option key={u._id} value={u._id}>
                {u.fileName}
              </option>
            ))}
          </select>
        </div>

        {/* Chat Messages */}
        <div className="flex-1 overflow-y-auto space-y-4 px-1">
          {messages.map((message) => (
            <ChatBubble key={message.id} message={message} />
          ))}

          {/* Loading Indicator */}
          {isLoading && (
            <div className="flex gap-3 animate-slide-up">
              <div className="w-8 h-8 bg-gradient-to-br from-blue-600 to-purple-600 rounded-full flex items-center justify-center flex-shrink-0">
                <span className="text-white text-xs font-bold">AI</span>
              </div>
              <div className="bg-gray-100 rounded-2xl rounded-bl-sm px-4 py-3">
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Reasoning Toggle */}
        <div className="flex items-center justify-between">
          <button
            onClick={toggleReasoning}
            className="flex items-center gap-2 px-3 py-1.5 text-xs text-gray-500 hover:text-gray-700 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            {showReasoning ? "Hide Reasoning" : "Show Reasoning"}
          </button>
          {chartData && (
            <span className="text-xs text-gray-400">
              Chart available for latest response
            </span>
          )}
        </div>

        {/* Chart Preview */}
        {chartData && (
          <div className="card p-4">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-900">Chart Preview</h3>
              <button
                onClick={() => setChartData(null)}
                className="text-xs text-gray-400 hover:text-gray-600"
              >
                Close ✕
              </button>
            </div>
            <ChartWidget
              data={chartData}
              height={300}
            />
          </div>
        )}

        {/* Suggested Questions */}
        {messages.length <= 2 && (
          <div className="mt-4 mb-3">
            <p className="text-xs text-gray-400 mb-2">Try asking:</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTED_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => handleSuggestedQuestion(q)}
                  className="px-3 py-1.5 bg-gray-100 hover:bg-gray-200 text-gray-600 hover:text-gray-900 rounded-full text-xs font-medium transition-colors"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Input Area */}
        <div className="mt-4 card p-3">
          <div className="flex items-end gap-3">
            <div className="flex-1">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask a question about your data..."
                className="w-full resize-none outline-none text-sm text-gray-900 placeholder:text-gray-400 bg-transparent max-h-32"
                rows={1}
                disabled={isLoading}
              />
            </div>
            <button
              onClick={handleSend}
              disabled={!input.trim() || isLoading}
              className="btn-primary !px-3 !py-2.5 flex-shrink-0"
            >
              {isLoading ? (
                <svg className="w-5 h-5 animate-spin" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                </svg>
              )}
            </button>
          </div>
        </div>
      </div>
    </Layout>
  );
}
