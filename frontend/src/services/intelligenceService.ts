import { apiClient } from "./api";
import {
  DocumentSummaryRequest,
  DocumentSummaryResponse,
  DocumentComparisonRequest,
  DocumentComparisonResponse,
  StructuredExtractionRequest,
  StructuredExtractionResponse,
  ReportGenerateRequest,
  ReportGenerateResponse,
} from "../types/intelligence";

export const intelligenceService = {
  async summarizeDocument(
    documentId: string,
    mode: "concise" | "detailed" = "concise",
    forceRefresh: boolean = false
  ): Promise<DocumentSummaryResponse> {
    const payload: DocumentSummaryRequest = {
      mode,
      force_refresh: forceRefresh,
    };
    const response = await apiClient.post<DocumentSummaryResponse>(
      `/documents/${documentId}/summarize`,
      payload
    );
    return response.data;
  },

  async compareDocuments(
    documentIds: string[],
    comparisonPrompt?: string
  ): Promise<DocumentComparisonResponse> {
    const payload: DocumentComparisonRequest = {
      document_ids: documentIds,
      comparison_prompt: comparisonPrompt,
    };
    const response = await apiClient.post<DocumentComparisonResponse>(
      "/documents/compare",
      payload
    );
    return response.data;
  },

  async extractStructured(
    documentId: string,
    targetFields?: string[]
  ): Promise<StructuredExtractionResponse> {
    const payload: StructuredExtractionRequest = {
      target_fields: targetFields,
    };
    const response = await apiClient.post<StructuredExtractionResponse>(
      `/documents/${documentId}/extract-structured`,
      payload
    );
    return response.data;
  },

  getStructuredCsvExportUrl(documentId: string): string {
    const baseURL = apiClient.defaults.baseURL || "/api/v1";
    return `${baseURL}/documents/${documentId}/extract-structured/export.csv`;
  },

  async generateReport(
    data: ReportGenerateRequest
  ): Promise<ReportGenerateResponse> {
    const response = await apiClient.post<ReportGenerateResponse>(
      "/reports/generate",
      data
    );
    return response.data;
  },
};
