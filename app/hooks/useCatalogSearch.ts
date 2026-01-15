import { useCallback, useState } from "react";
import { useAsync } from "@databiosphere/findable-ui/lib/hooks/useAsync";
import { llmAPIClient } from "../services/llm-api-client";
import { CatalogSearchResponse } from "../types/api";

interface SubmitOptions {
  onError: (error: Error) => void;
  onSuccess: () => void;
}

interface UseCatalogSearchReturn {
  clearSession: () => void;
  data: CatalogSearchResponse | undefined;
  search: (query: string) => Promise<void>;
  sessionId: string | undefined;
  status: {
    errors: Record<string, string>;
    loading: boolean;
  };
}

/**
 * Perform catalog search with session support
 * @param root0 - Search parameters
 * @param root0.query - Natural language query
 * @param root0.sessionId - Optional session ID for multi-turn conversation
 * @param root0.submitOptions - Success/error callbacks
 * @returns Search response or undefined on error
 */
async function performCatalogSearch({
  query,
  sessionId,
  submitOptions,
}: {
  query: string;
  sessionId?: string;
  submitOptions: SubmitOptions;
}): Promise<CatalogSearchResponse | undefined> {
  try {
    const result = await llmAPIClient.catalogSearch({
      query,
      session_id: sessionId,
    });
    submitOptions.onSuccess();
    return result;
  } catch (error) {
    submitOptions.onError(error as Error);
    return undefined;
  }
}

/**
 * Custom hook for conversational catalog search
 * Supports multi-turn conversations with session persistence
 * @returns Object with data, search function, session info, and status
 */
export const useCatalogSearch = (): UseCatalogSearchReturn => {
  const { data, run } = useAsync<CatalogSearchResponse | undefined>();
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState<boolean>(false);
  const [sessionId, setSessionId] = useState<string | undefined>();

  const search = useCallback(
    async (query: string): Promise<void> => {
      if (!query.trim()) {
        setErrors({ query: "Search query cannot be empty" });
        return;
      }

      setLoading(true);
      setErrors({});

      run(
        performCatalogSearch({
          query,
          sessionId,
          submitOptions: {
            onError: (e) => {
              const errorMessage = handleSearchError(e);
              setErrors({ search: errorMessage });
              setLoading(false);
            },
            onSuccess: () => {
              setLoading(false);
            },
          },
        }).then((result) => {
          if (result?.session_id) {
            setSessionId(result.session_id);
          }
          return result;
        })
      );
    },
    [run, sessionId]
  );

  const clearSession = useCallback(() => {
    setSessionId(undefined);
  }, []);

  return { clearSession, data, search, sessionId, status: { errors, loading } };
};

/**
 * Handle different types of API errors and provide user-friendly messages
 * @param error - Error from API call
 * @returns User-friendly error message
 */
function handleSearchError(error: unknown): string {
  const err = error as { message?: string; name?: string };
  if (err.name === "TimeoutError") {
    return "Search timed out. Please try again.";
  } else if (err.message?.includes("503")) {
    return "Catalog service temporarily unavailable. Please try again later.";
  } else if (err.message?.includes("429")) {
    return "Too many requests. Please wait a moment and try again.";
  } else if (err.message?.includes("500")) {
    return "Internal server error. Please try again later.";
  } else {
    return "Search failed. Please check your query and try again.";
  }
}
