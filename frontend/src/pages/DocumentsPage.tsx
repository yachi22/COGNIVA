import React, { useState } from "react";
import { useParams } from "react-router-dom";
import { Files, Folder, FileText } from "lucide-react";
import DocumentTable from "../components/documents/DocumentTable";
import UploadDropzone from "../components/documents/UploadDropzone";
import CollectionModal from "../components/documents/CollectionModal";
import ReportModal from "../components/documents/ReportModal";
import Button from "../components/common/Button";
import useDocuments from "../hooks/useDocuments";

export const DocumentsPage: React.FC = () => {
  const { documentId } = useParams<{ documentId?: string }>();
  const {
    documents,
    isLoading,
    isUploading,
    uploadProgress,
    uploadError,
    uploadSuccess,
    processingIds,
    uploadFile,
    processDoc,
    getExtracted,
    deleteDoc,
    clearUploadStatus,
  } = useDocuments();

  const [showCollections, setShowCollections] = useState(false);
  const [showReportModal, setShowReportModal] = useState(false);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-lg sm:text-xl font-bold text-primary tracking-tight flex items-center gap-2">
            <Files className="w-5 h-5 text-accent" />
            Knowledge Document Repository
          </h1>
          <p className="text-xs sm:text-sm text-secondary mt-0.5">
            Ingest and manage enterprise documentation. Supported formats: Adobe PDF (.pdf), Microsoft Word (.docx), and Structured Data (.csv).
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="xs"
            onClick={() => setShowCollections(true)}
            className="flex items-center gap-1.5 text-xs"
          >
            <Folder className="w-3.5 h-3.5 text-accent" />
            Collections
          </Button>
          <Button
            variant="outline"
            size="xs"
            onClick={() => setShowReportModal(true)}
            className="flex items-center gap-1.5 text-xs"
          >
            <FileText className="w-3.5 h-3.5 text-accent" />
            Generate Report
          </Button>
          <span className="text-xs font-medium px-2.5 py-1 rounded bg-panel text-primary border border-border">
            {documents.length} {documents.length === 1 ? "Indexed Asset" : "Indexed Assets"}
          </span>
        </div>
      </div>

      {/* Upload Dropzone */}
      <UploadDropzone
        onUpload={uploadFile}
        isUploading={isUploading}
        uploadProgress={uploadProgress}
        uploadError={uploadError}
        uploadSuccess={uploadSuccess}
        onClearStatus={clearUploadStatus}
      />

      {/* Document Table with processing, inspection, and intelligence actions */}
      <DocumentTable
        documents={documents}
        isLoading={isLoading}
        processingIds={processingIds}
        onProcess={processDoc}
        onViewExtracted={getExtracted}
        onDelete={deleteDoc}
        initialViewerDocId={documentId}
      />

      {/* Standalone Modals */}
      {showCollections && (
        <CollectionModal onClose={() => setShowCollections(false)} />
      )}
      {showReportModal && (
        <ReportModal
          documents={documents}
          onClose={() => setShowReportModal(false)}
        />
      )}
    </div>
  );
};

export default DocumentsPage;
