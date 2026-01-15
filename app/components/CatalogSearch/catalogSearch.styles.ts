import styled from "@emotion/styled";
import { Box, Paper } from "@mui/material";

export const SearchContainer = styled(Box)`
  margin: 0 auto;
  max-width: 1200px;
  padding: 0 16px;
`;

export const SearchFormContainer = styled(Box)`
  margin-bottom: 24px;
`;

export const SearchForm = styled(Box)`
  align-items: flex-start;
  display: flex;
  gap: 16px;
`;

export const SearchHelperText = styled(Box)`
  margin-top: 8px;
`;

export const ConversationContainer = styled(Box)`
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 24px;
`;

export const MessageBubble = styled(Paper)<{ isUser?: boolean }>`
  background-color: ${({ isUser }): string => (isUser ? "#e3f2fd" : "#f5f5f5")};
  border-radius: 12px;
  margin-left: ${({ isUser }): string => (isUser ? "auto" : "0")};
  margin-right: ${({ isUser }): string => (isUser ? "0" : "auto")};
  max-width: 80%;
  padding: 12px 16px;
`;

export const FiltersContainer = styled(Box)`
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
`;

export const ResultsContainer = styled(Box)`
  margin-top: 24px;
`;

export const ResultCard = styled(Paper)`
  margin-bottom: 12px;
  padding: 16px;
`;

export const SessionInfo = styled(Box)`
  align-items: center;
  background-color: #fff3e0;
  border-radius: 8px;
  display: flex;
  gap: 8px;
  justify-content: space-between;
  margin-bottom: 16px;
  padding: 8px 16px;
`;
