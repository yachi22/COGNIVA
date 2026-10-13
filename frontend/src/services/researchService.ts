import { apiClient } from "./api";
import {
  DeepResearchRequest,
  DeepResearchResponse,
  KnowledgeGraphResponse,
} from "../types/intelligence";

export const researchService = {
  async executeDeepResearch(
    data: DeepResearchRequest
  ): Promise<DeepResearchResponse> {
    const response = await apiClient.post<DeepResearchResponse>(
      "/research/deep-query",
      data
    );
    return response.data;
  },

  async getKnowledgeGraph(
    documentId?: string,
    maxChunks: number = 8
  ): Promise<KnowledgeGraphResponse> {
    const params: Record<string, any> = { max_chunks: maxChunks };
    if (documentId) {
      params.document_id = documentId;
    }
    const response = await apiClient.get<KnowledgeGraphResponse>(
      "/knowledge-graph",
      { params }
    );
    return response.data;
  },
};
