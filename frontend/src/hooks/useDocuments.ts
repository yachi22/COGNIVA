import { useState, useEffect, useCallback, useRef } from "react";
import { documentService } from "../services/documentService";
import { DocumentItem, ExtractedDocument, DocumentJob } from "../types/document";

export const useDocuments = () => {
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);

  const [processingIds, setProcessingIds] = useState<Record<string, boolean>>({});
  const [jobStates, setJobStates] = useState<Record<string, DocumentJob>>({});
  const pollingTimers = useRef<Record<string, ReturnType<typeof setInterval>>>({});

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

  const stopPolling = useCallback((id: string) => {
    if (pollingTimers.current[id]) {
      clearInterval(pollingTimers.current[id]);
      delete pollingTimers.current[id];
    }
  }, []);

  const pollJobStatus = useCallback(
    (id: string) => {
      stopPolling(id);
      const timer = setInterval(async () => {
        try {
          const job = await documentService.getLatestJob(id);
          setJobStates((prev) => ({ ...prev, [id]: job }));

          if (job.status === "completed") {
            stopPolling(id);
            setProcessingIds((prev) => {
              const next = { ...prev };
              delete next[id];
              return next;
            });
            setDocuments((prev) =>
              prev.map((doc) => (doc.id === id ? { ...doc, status: "processed" } : doc))
            );
            fetchDocuments();
          } else if (job.status === "failed") {
            stopPolling(id);
            setProcessingIds((prev) => {
              const next = { ...prev };
              delete next[id];
              return next;
            });
            setDocuments((prev) =>
              prev.map((doc) => (doc.id === id ? { ...doc, status: "failed" } : doc))
            );
            if (job.error_message) {
              setError(job.error_message);
            }
            fetchDocuments();
          }
        } catch (err: any) {
          // If 404 or connection error, check document status directly
          try {
            const doc = await documentService.getDocument(id);
            if (doc.status !== "processing") {
              stopPolling(id);
              setProcessingIds((prev) => {
                const next = { ...prev };
                delete next[id];
                return next;
              });
              setDocuments((prev) =>
                prev.map((d) => (d.id === id ? doc : d))
              );
            }
          } catch (_) {}
        }
      }, 1500);

      pollingTimers.current[id] = timer;
    },
    [fetchDocuments, stopPolling]
  );

  // Resume polling for any documents already in 'processing' status
  useEffect(() => {
    documents.forEach((doc) => {
      if (doc.status === "processing" && !pollingTimers.current[doc.id]) {
        setProcessingIds((prev) => ({ ...prev, [doc.id]: true }));
        pollJobStatus(doc.id);
      }
    });

    return () => {
      Object.keys(pollingTimers.current).forEach((id) => {
        clearInterval(pollingTimers.current[id]);
      });
      pollingTimers.current = {};
    };
  }, [documents, pollJobStatus]);

  const processDoc = async (id: string): Promise<DocumentItem | null> => {
    setProcessingIds((prev) => ({ ...prev, [id]: true }));
    // Optimistic status update
    setDocuments((prev) =>
      prev.map((doc) => (doc.id === id ? { ...doc, status: "processing" } : doc))
    );

    try {
      const updatedDoc = await documentService.processDocument(id, true);
      setDocuments((prev) =>
        prev.map((doc) => (doc.id === id ? updatedDoc : doc))
      );
      // Start polling live background job
      pollJobStatus(id);
      return updatedDoc;
    } catch (err: any) {
      const message =
        err.response?.data?.detail || "Document text extraction failed.";
      setError(message);
      setProcessingIds((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      await fetchDocuments();
      return null;
    }
  };

  const retryDocJob = async (documentId: string, jobId: string) => {
    try {
      setProcessingIds((prev) => ({ ...prev, [documentId]: true }));
      const job = await documentService.retryDocumentJob(documentId, jobId);
      setJobStates((prev) => ({ ...prev, [documentId]: job }));
      pollJobStatus(documentId);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to retry processing job.");
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
    jobStates,
    fetchDocuments,
    uploadFile,
    processDoc,
    retryDocJob,
    getExtracted,
    deleteDoc,
    clearUploadStatus,
  };
};

export default useDocuments;
