import { useCallback, useEffect, useRef, useState } from "react";
import { brcAPIClient } from "../services/brc-api-client";
import { llmAPIClient } from "../services/llm-api-client";
import {
  AnalysisSchema,
  AssistantChatResponse,
  SavedAnalysisDetail,
  SuggestionChip,
} from "../types/api";

interface ChatMessageDisplay {
  content: string;
  role: "user" | "assistant";
}

interface UseAssistantChatReturn {
  error: string | null;
  handoffUrl: string | null;
  isComplete: boolean;
  loading: boolean;
  messages: ChatMessageDisplay[];
  saveAnalysis: () => Promise<void>;
  saveLoading: boolean;
  saveMessage: string | null;
  schema: AnalysisSchema | null;
  sendMessage: (message: string) => Promise<void>;
  suggestions: SuggestionChip[];
}

interface UseAssistantChatOptions {
  initialSavedAnalysisId?: string;
  initialSessionId?: string;
}

/**
 * Manages assistant chat state: messages, session, schema, and suggestions.
 * @param root0 - Hook options.
 * @param root0.initialSavedAnalysisId - Saved analysis to hydrate into the chat.
 * @param root0.initialSessionId - Existing assistant session to continue.
 * @returns Chat state and a sendMessage function
 */
export const useAssistantChat = ({
  initialSavedAnalysisId,
  initialSessionId,
}: UseAssistantChatOptions = {}): UseAssistantChatReturn => {
  const [messages, setMessages] = useState<ChatMessageDisplay[]>([]);
  const [schema, setSchema] = useState<AnalysisSchema | null>(null);
  const [suggestions, setSuggestions] = useState<SuggestionChip[]>([]);
  const [isComplete, setIsComplete] = useState(false);
  const [handoffUrl, setHandoffUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveLoading, setSaveLoading] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const sessionIdRef = useRef<string | null>(initialSessionId ?? null);

  useEffect(() => {
    sessionIdRef.current = initialSessionId ?? null;
  }, [initialSessionId]);

  useEffect(() => {
    if (!initialSavedAnalysisId) return;

    let isMounted = true;
    setError(null);

    brcAPIClient
      .getSavedAnalysis(initialSavedAnalysisId)
      .then((savedAnalysis: SavedAnalysisDetail) => {
        if (!isMounted) return;
        setMessages(savedAnalysis.messages);
        setSchema(savedAnalysis.schema);
      })
      .catch(() => {
        if (!isMounted) return;
        setError("Failed to restore the saved analysis.");
      });

    return (): void => {
      isMounted = false;
    };
  }, [initialSavedAnalysisId]);

  const sendMessage = useCallback(async (message: string): Promise<void> => {
    if (!message.trim()) return;

    setLoading(true);
    setError(null);
    setSaveMessage(null);

    // Add user message immediately for responsiveness
    setMessages((prev) => [...prev, { content: message, role: "user" }]);

    try {
      const response: AssistantChatResponse = await llmAPIClient.assistantChat({
        message,
        session_id: sessionIdRef.current ?? undefined,
      });

      sessionIdRef.current = response.session_id;

      // Add assistant reply
      setMessages((prev) => [
        ...prev,
        { content: response.reply, role: "assistant" },
      ]);

      setSchema(response.schema_state);
      setSuggestions(response.suggestions);
      setIsComplete(response.is_complete);
      setHandoffUrl(response.handoff_url);
    } catch (err) {
      const errorMessage = handleChatError(err);
      setError(errorMessage);
      // Remove the user message if the request failed entirely
      setMessages((prev) => prev.slice(0, -1));
    } finally {
      setLoading(false);
    }
  }, []);

  const saveAnalysis = useCallback(async (): Promise<void> => {
    if (!sessionIdRef.current) {
      setSaveMessage("There is no active assistant session to save.");
      return;
    }

    setSaveLoading(true);
    setSaveMessage(null);
    try {
      const savedAnalysis = await brcAPIClient.saveAnalysis(
        sessionIdRef.current
      );
      setSaveMessage(
        savedAnalysis.title ? `Saved: ${savedAnalysis.title}` : "Saved."
      );
    } catch {
      setSaveMessage("Failed to save this analysis.");
    } finally {
      setSaveLoading(false);
    }
  }, []);

  return {
    error,
    handoffUrl,
    isComplete,
    loading,
    messages,
    saveAnalysis,
    saveLoading,
    saveMessage,
    schema,
    sendMessage,
    suggestions,
  };
};

/**
 * Map API errors to user-friendly messages.
 * @param error - The caught error
 * @returns A user-facing error string
 */
function handleChatError(error: unknown): string {
  const err = error as { message?: string; name?: string };
  if (err.name === "TimeoutError") {
    return "The assistant took too long to respond. Please try again.";
  } else if (err.message?.includes("503")) {
    return "The analysis assistant is currently unavailable. Please try again later.";
  } else if (err.message?.includes("429")) {
    return "Too many requests. Please wait a moment and try again.";
  }
  return "Something went wrong. Please try again.";
}
