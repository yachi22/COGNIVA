import { apiClient } from "./api";
import {
  CollectionItem,
  CollectionCreate,
  CollectionUpdate,
  CollectionListResponse,
} from "../types/collection";

export const collectionService = {
  async getCollections(): Promise<CollectionListResponse> {
    const response = await apiClient.get<any>("/collections");
    if (Array.isArray(response.data)) {
      return { items: response.data, total: response.data.length };
    }
    return response.data || { items: [], total: 0 };
  },

  async getCollection(id: string): Promise<CollectionItem> {
    const response = await apiClient.get<CollectionItem>(`/collections/${id}`);
    return response.data;
  },

  async createCollection(data: CollectionCreate): Promise<CollectionItem> {
    const response = await apiClient.post<CollectionItem>("/collections", data);
    return response.data;
  },

  async updateCollection(
    id: string,
    data: CollectionUpdate
  ): Promise<CollectionItem> {
    const response = await apiClient.put<CollectionItem>(
      `/collections/${id}`,
      data
    );
    return response.data;
  },

  async deleteCollection(id: string): Promise<{ success: boolean }> {
    const response = await apiClient.delete<{ success: boolean }>(
      `/collections/${id}`
    );
    return response.data;
  },

  async addDocument(
    collectionId: string,
    documentId: string
  ): Promise<{ success: boolean; message: string }> {
    const response = await apiClient.post<{ success: boolean; message: string }>(
      `/collections/${collectionId}/documents`,
      { document_id: documentId }
    );
    return response.data;
  },

  async removeDocument(
    collectionId: string,
    documentId: string
  ): Promise<{ success: boolean; message: string }> {
    const response = await apiClient.delete<{
      success: boolean;
      message: string;
    }>(`/collections/${collectionId}/documents/${documentId}`);
    return response.data;
  },
};
