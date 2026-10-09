import apiClient from "./api";
import {
  RAGQueryRequest,
  RAGQueryResponse,
  ConversationResponse,
  ConversationDetailResponse,
  ConversationListResponse,
} from "../types/chat";

export const queryRAG = async (data: RAGQueryRequest): Promise<RAGQueryResponse> => {
  const response = await apiClient.post<RAGQueryResponse>("/rag/query", data);
  return response.data;
};

export const listConversations = async (
  skip: number = 0,
  limit: number = 50,
): Promise<ConversationListResponse> => {
  const response = await apiClient.get<ConversationListResponse>("/conversations", {
    params: { skip, limit },
  });
  return response.data;
};

export const getConversation = async (
  conversationId: string,
): Promise<ConversationDetailResponse> => {
  const response = await apiClient.get<ConversationDetailResponse>(
    `/conversations/${conversationId}`,
  );
  return response.data;
};

export const createConversation = async (
  title?: string,
): Promise<ConversationResponse> => {
  const response = await apiClient.post<ConversationResponse>("/conversations", {
    title: title || undefined,
  });
  return response.data;
};

export const deleteConversation = async (conversationId: string): Promise<void> => {
  await apiClient.delete(`/conversations/${conversationId}`);
};
