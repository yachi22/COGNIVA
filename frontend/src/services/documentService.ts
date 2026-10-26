import apiClient from "./api";
import {
  DocumentItem,
  DocumentDeleteResponse,
  ExtractedDocument,
  DocumentChunkListResponse,
  DocumentChunkDetail,
} from "../types/document";

export const documentService = {
  /**
   * Fetch all documents belonging to the authenticated user.
   */
  async getDocuments(): Promise<DocumentItem[]> {
    const response = await apiClient.get<DocumentItem[]>("/documents");
    return response.data;
  },

  /**
   * Fetch a single document by ID.
   */
  async getDocument(id: string): Promise<DocumentItem> {
    const response = await apiClient.get<DocumentItem>(`/documents/${id}`);
    return response.data;
  },

  /**
   * Upload a PDF or DOCX file to the enterprise document repository.
   */
  async uploadDocument(
    file: File,
    onProgress?: (progressPercent: number) => void
  ): Promise<DocumentItem> {
    const formData = new FormData();
    formData.append("file", file);

    const response = await apiClient.post<DocumentItem>("/documents", formData, {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total && onProgress) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(percent);
        }
      },
    });

    return response.data;
  },

  /**
   * Trigger synchronous text extraction pipeline for a document.
   */
  async processDocument(id: string): Promise<DocumentItem> {
    const response = await apiClient.post<DocumentItem>(`/documents/${id}/process`);
    return response.data;
  },

  /**
   * Retrieve normalized extracted units and provenance for a processed document.
   */
  async getExtractedContent(id: string): Promise<ExtractedDocument> {
    const response = await apiClient.get<ExtractedDocument>(`/documents/${id}/extracted`);
    return response.data;
  },

  /**
   * Retrieve all chunks for a document.
   */
  async getDocumentChunks(documentId: string): Promise<DocumentChunkListResponse> {
    const response = await apiClient.get<DocumentChunkListResponse>(`/documents/${documentId}/chunks`);
    return response.data;
  },

  /**
   * Delete a document belonging to the authenticated user.
   */
  async deleteDocument(id: string): Promise<DocumentDeleteResponse> {
    const response = await apiClient.delete<DocumentDeleteResponse>(`/documents/${id}`);
    return response.data;
  },

  /**
   * Retrieve a single document chunk for citation/source inspection.
   */
  async getDocumentChunk(documentId: string, chunkId: string): Promise<DocumentChunkDetail> {
    const response = await apiClient.get<DocumentChunkDetail>(`/documents/${documentId}/chunks/${chunkId}`);
    return response.data;
  },

  /**
   * Download authentic original document binary.
   */
  async downloadDocument(id: string, filename: string): Promise<void> {
    const response = await apiClient.get(`/documents/${id}/download?redirect=false`, {
      responseType: "blob",
    });
    const blob = new Blob([response.data]);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  },
};

export default documentService;

