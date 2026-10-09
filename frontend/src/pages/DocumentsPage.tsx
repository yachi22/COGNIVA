import React from "react";
import { Files } from "lucide-react";
import DocumentTable from "../components/documents/DocumentTable";
import UploadDropzone from "../components/documents/UploadDropzone";
import useDocuments from "../hooks/useDocuments";

export const DocumentsPage: React.FC = () => {
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

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900 tracking-tight flex items-center gap-2.5">
            <Files className="w-6 h-6 text-indigo-600" />
            Document Repository
          </h1>
          <p className="text-xs sm:text-sm text-slate-500 mt-1">
            Upload and manage your enterprise knowledge sources. Supported formats: PDF (.pdf) and Word (.docx).
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold px-3 py-1.5 rounded-lg bg-indigo-50 text-indigo-700 border border-indigo-100">
            {documents.length} {documents.length === 1 ? "Document" : "Documents"}
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

      {/* Document Table with processing and inspection */}
      <DocumentTable
        documents={documents}
        isLoading={isLoading}
        processingIds={processingIds}
        onProcess={processDoc}
        onViewExtracted={getExtracted}
        onDelete={deleteDoc}
      />
    </div>
  );
};

export default DocumentsPage;
