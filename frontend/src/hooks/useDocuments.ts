import { useState, useEffect, useCallback } from "react";
import { documentService } from "../services/documentService";
import { DocumentItem, ExtractedDocument } from "../types/document";

export const useDocuments = () => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);

  const [processingIds, setProcessingIds] = useState<Record<string, boolean>>({});

  const fetchDocuments = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await documentService.getDocuments();
      setDocuments(data);
    } catch (err: any) {
      const message =
        err.response?.data?.detail || "Failed to load documents. Please try again.";
      setError(message);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  const uploadFile = async (file: File): Promise<DocumentItem | null> => {
    setIsUploading(true);
    setUploadProgress(0);
    setUploadError(null);
    setUploadSuccess(null);

    try {
      const newDoc = await documentService.uploadDocument(file, (percent) => {
        setUploadProgress(percent);
      });
      setUploadSuccess(`"${file.name}" uploaded successfully.`);
      // Optimistically prepend to list
      setDocuments((prev) => [newDoc, ...prev]);
      return newDoc;
    } catch (err: any) {
      const message =
        err.response?.data?.detail ||
        err.message ||
        "Upload failed. Please ensure the file is a valid PDF or DOCX under 50MB.";
      setUploadError(message);
      return null;
    } finally {
      setIsUploading(false);
    }
  };

  const processDoc = async (id: string): Promise<DocumentItem | null> => {
    setProcessingIds((prev) => ({ ...prev, [id]: true }));
    // Optimistic status update
    setDocuments((prev) =>
      prev.map((doc) => (doc.id === id ? { ...doc, status: "processing" } : doc))
    );

    try {
      const updatedDoc = await documentService.processDocument(id);
      setDocuments((prev) =>
        prev.map((doc) => (doc.id === id ? updatedDoc : doc))
      );
      return updatedDoc;
    } catch (err: any) {
      const message =
        err.response?.data?.detail || "Document text extraction failed.";
      setError(message);
      // Refresh documents from backend to reflect true failed status
      await fetchDocuments();
      return null;
    } finally {
      setProcessingIds((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
    }
  };

  const getExtracted = async (id: string): Promise<ExtractedDocument | null> => {
    try {
      return await documentService.getExtractedContent(id);
    } catch (err: any) {
      const message =
        err.response?.data?.detail || "Failed to fetch extracted document content.";
      setError(message);
      return null;
    }
  };

  const deleteDoc = async (id: string): Promise<boolean> => {
    try {
      await documentService.deleteDocument(id);
      setDocuments((prev) => prev.filter((doc) => doc.id !== id));
      return true;
    } catch (err: any) {
      const message =
        err.response?.data?.detail || "Failed to delete document. Please try again.";
      setError(message);
      return false;
    }
  };

  const clearUploadStatus = () => {
    setUploadError(null);
    setUploadSuccess(null);
    setUploadProgress(0);
  };

  return {
    documents,
    isLoading,
    error,
    isUploading,
    uploadProgress,
    uploadError,
    uploadSuccess,
    processingIds,
    fetchDocuments,
    uploadFile,
    processDoc,
    getExtracted,
    deleteDoc,
    clearUploadStatus,
  };
};

export default useDocuments;
