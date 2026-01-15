import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Chip,
  CircularProgress,
  IconButton,
  Link,
  TextField,
  Tooltip,
  Typography,
} from "@mui/material";
import RefreshIcon from "@mui/icons-material/Refresh";
import { useCatalogSearch } from "../../hooks/useCatalogSearch";
import { CatalogAssembly, CatalogSearchFilter } from "../../types/api";
import {
  ConversationContainer,
  FiltersContainer,
  MessageBubble,
  ResultCard,
  ResultsContainer,
  SearchContainer,
  SearchForm,
  SearchFormContainer,
  SearchHelperText,
  SessionInfo,
} from "./catalogSearch.styles";

interface ConversationMessage {
  content: string;
  isUser: boolean;
}

/**
 * Format a number with commas for readability
 * @param num - Number to format
 * @returns Formatted string
 */
const formatNumber = (num: number | undefined): string => {
  if (num === undefined) return "N/A";
  return num.toLocaleString();
};

/**
 * Get button label based on state
 * @param isLoading - Whether search is in progress
 * @param hasSession - Whether there's an active session
 * @returns Button label text
 */
const getButtonLabel = (isLoading: boolean, hasSession: boolean): string => {
  if (isLoading) return "...";
  if (hasSession) return "Refine";
  return "Search";
};

/**
 * Render a single assembly result card
 * @param props - Component props
 * @param props.assembly - Assembly data to render
 * @returns JSX element
 */
const AssemblyCard = ({
  assembly,
}: {
  assembly: CatalogAssembly;
}): JSX.Element => (
  <ResultCard elevation={1}>
    <Box sx={{ display: "flex", justifyContent: "space-between", mb: 1 }}>
      <Typography variant="h6" component="span">
        {assembly.accession}
      </Typography>
      <Box sx={{ display: "flex", gap: 1 }}>
        {assembly.isRef === "Yes" && (
          <Chip label="Reference" color="primary" size="small" />
        )}
        {assembly.level && (
          <Chip label={assembly.level} variant="outlined" size="small" />
        )}
      </Box>
    </Box>

    <Typography variant="body1" color="text.secondary" gutterBottom>
      {assembly.taxonomicLevelSpecies || assembly.taxonomicLevelGenus}
      {assembly.strainName && ` (${assembly.strainName})`}
    </Typography>

    <Box
      sx={{ display: "grid", gap: 1, gridTemplateColumns: "repeat(3, 1fr)" }}
    >
      <Typography variant="body2">
        <strong>Domain:</strong> {assembly.taxonomicLevelDomain || "N/A"}
      </Typography>
      <Typography variant="body2">
        <strong>Scaffolds:</strong> {formatNumber(assembly.scaffoldCount)}
      </Typography>
      <Typography variant="body2">
        <strong>Length:</strong> {formatNumber(assembly.length)} bp
      </Typography>
      <Typography variant="body2">
        <strong>GC%:</strong> {assembly.gcPercent ?? "N/A"}
      </Typography>
      <Typography variant="body2">
        <strong>Chromosomes:</strong> {assembly.chromosomes ?? "N/A"}
      </Typography>
      <Typography variant="body2">
        <strong>Ploidy:</strong> {assembly.ploidy?.join(", ") || "N/A"}
      </Typography>
    </Box>

    <Box sx={{ display: "flex", gap: 2, mt: 2 }}>
      {assembly.ucscBrowserUrl && (
        <Link
          href={assembly.ucscBrowserUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          UCSC Browser
        </Link>
      )}
      {assembly.geneModelUrl && (
        <Link
          href={assembly.geneModelUrl}
          target="_blank"
          rel="noopener noreferrer"
        >
          Gene Model (GTF)
        </Link>
      )}
    </Box>
  </ResultCard>
);

/**
 * Render applied filters as chips
 * @param props - Component props
 * @param props.filters - Array of applied filters
 * @returns JSX element
 */
const AppliedFilters = ({
  filters,
}: {
  filters: CatalogSearchFilter[];
}): JSX.Element | null => {
  if (filters.length === 0) return null;

  return (
    <FiltersContainer>
      <Typography variant="body2" sx={{ mr: 1 }}>
        Filters:
      </Typography>
      {filters.map((filter, index) => (
        <Chip
          key={index}
          label={`${filter.column} ${filter.operator} "${filter.value}"`}
          size="small"
          variant="outlined"
        />
      ))}
    </FiltersContainer>
  );
};

export const CatalogSearch = (): JSX.Element => {
  const [query, setQuery] = useState("");
  const [conversation, setConversation] = useState<ConversationMessage[]>([]);
  const { clearSession, data, search, sessionId, status } = useCatalogSearch();

  const handleSearch = (): void => {
    if (!query.trim()) return;

    // Add user message to conversation
    setConversation((prev) => [...prev, { content: query, isUser: true }]);

    search(query).then(() => {
      // Response will be shown via data
    });

    setQuery("");
  };

  const handleKeyPress = (e: React.KeyboardEvent): void => {
    if (e.key === "Enter" && !e.shiftKey && !status.loading && query.trim()) {
      e.preventDefault();
      handleSearch();
    }
  };

  const handleNewConversation = (): void => {
    clearSession();
    setConversation([]);
  };

  const hasError = !!status.errors.query || !!status.errors.search;
  const errorMessage = status.errors.query || status.errors.search;

  // Add system response to conversation when data changes
  useEffect(() => {
    if (!data?.message || conversation.length === 0) return;

    const lastMessage = conversation[conversation.length - 1];
    if (!lastMessage.isUser) return;

    const responseExists = conversation.some(
      (msg) => !msg.isUser && msg.content === data.message
    );
    if (responseExists) return;

    setConversation((prev) => [
      ...prev,
      { content: data.message, isUser: false },
    ]);
  }, [data?.message, conversation]);

  return (
    <SearchContainer>
      {sessionId && (
        <SessionInfo>
          <Typography variant="body2">
            Conversation active (Turn {data?.turn_count || 1})
          </Typography>
          <Tooltip title="Start new conversation">
            <IconButton size="small" onClick={handleNewConversation}>
              <RefreshIcon />
            </IconButton>
          </Tooltip>
        </SessionInfo>
      )}

      {conversation.length > 0 && (
        <ConversationContainer>
          {conversation.map((msg, index) => (
            <MessageBubble key={index} isUser={msg.isUser} elevation={0}>
              <Typography variant="body2">{msg.content}</Typography>
            </MessageBubble>
          ))}
          {status.loading && (
            <MessageBubble isUser={false} elevation={0}>
              <Box sx={{ alignItems: "center", display: "flex", gap: 1 }}>
                <CircularProgress size={16} />
                <Typography variant="body2">Searching...</Typography>
              </Box>
            </MessageBubble>
          )}
        </ConversationContainer>
      )}

      <SearchFormContainer>
        <SearchForm>
          <TextField
            fullWidth
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder={
              sessionId
                ? "Refine your search (e.g., 'only reference genomes')"
                : "Describe what you're looking for..."
            }
            variant="outlined"
            error={hasError}
            helperText={hasError ? errorMessage : ""}
            disabled={status.loading}
            multiline
            rows={2}
            sx={{
              "& .MuiInputBase-multiline": { padding: 0 },
              "& .MuiOutlinedInput-notchedOutline": {
                borderColor: "rgba(0, 0, 0, 0.23)",
              },
              "& .MuiOutlinedInput-root": {
                fontSize: "16px",
                lineHeight: "24px",
                padding: "12px 16px",
              },
            }}
          />

          <Button
            onClick={handleSearch}
            disabled={status.loading || !query.trim()}
            variant="contained"
            size="large"
            sx={{
              alignSelf: "flex-start",
              height: "56px",
              minWidth: "120px",
            }}
          >
            {getButtonLabel(status.loading, !!sessionId)}
          </Button>
        </SearchForm>

        <SearchHelperText>
          <Typography variant="body2" color="text.secondary">
            {sessionId
              ? 'Try: "only show reference genomes" or "filter to Plasmodium falciparum"'
              : 'Try: "complete malaria genomes" or "bacterial reference assemblies"'}
          </Typography>
        </SearchHelperText>
      </SearchFormContainer>

      {data && (
        <ResultsContainer>
          <AppliedFilters filters={data.filters_applied} />

          <Typography variant="h6" gutterBottom>
            {data.success
              ? `Found ${data.total_count} assemblies`
              : "Search completed"}
          </Typography>

          {data.results.length > 0 ? (
            <>
              {data.results.slice(0, 20).map((assembly) => (
                <AssemblyCard key={assembly.accession} assembly={assembly} />
              ))}
              {data.results.length > 20 && (
                <Alert severity="info" sx={{ mt: 2 }}>
                  Showing first 20 of {data.total_count} results. Refine your
                  search to narrow down.
                </Alert>
              )}
            </>
          ) : (
            <Alert severity="info">
              No assemblies match your criteria. Try broadening your search or
              using different terms.
            </Alert>
          )}
        </ResultsContainer>
      )}

      {!data && !status.loading && conversation.length === 0 && (
        <Box sx={{ mt: 4, textAlign: "center" }}>
          <Typography variant="body1" color="text.secondary">
            Search our catalog of {">"}5,000 genome assemblies using natural
            language.
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
            You can refine results progressively - just ask follow-up questions!
          </Typography>
        </Box>
      )}
    </SearchContainer>
  );
};
