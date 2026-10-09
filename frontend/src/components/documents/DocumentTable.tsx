import React, { useState } from "react";
import {
  Search,
  FileText,
  Trash2,
  Upload,
  Calendar,
  HardDrive,
  Loader2,
  Cpu,
  CheckCircle2,
  AlertCircle,
  Eye,
  X,
  Layers,
} from "lucide-react";
import Button from "../common/Button";
import EmptyState from "../common/EmptyState";
import Badge from "../common/Badge";
import { DocumentItem, ExtractedDocument } from "../../types/document";

interface DocumentTableProps {
  documents: DocumentItem[];
  isLoading?: boolean;
  processingIds?: Record<string, boolean>;
  onDelete?: (id: string) => Promise<boolean | unknown>;
  onProcess?: (id: string) => Promise<unknown>;
  onViewExtracted?: (id: string) => Promise<ExtractedDocument | null>;
  onUploadClick?: () => void;
}

export const DocumentTable: React.FC<DocumentTableProps> = ({
  documents = [],
  isLoading = false,
  processingIds = {},
  onDelete,
  onProcess,
  onViewExtracted,
  onUploadClick,
}) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  // Modal inspection state for extracted text
  const [inspectDoc, setInspectDoc] = useState<DocumentItem | null>(null);
  const [extractedData, setExtractedData] = useState<ExtractedDocument | null>(null);
  const [loadingExtracted, setLoadingExtracted] = useState(false);

  const filteredDocs = documents.filter((doc) => {
    const name = (doc.original_filename || doc.filename || "").toLowerCase();
    const type = (doc.file_type || "").toLowerCase();
    const status = (doc.status || "").toLowerCase();
    const term = searchTerm.toLowerCase();
    return name.includes(term) || type.includes(term) || status.includes(term);
  });

  const formatFileSize = (bytes?: number): string => {
    if (!bytes || bytes === 0) return "--";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (dateStr: string): string => {
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return dateStr;
    }
  };

  const handleDelete = async (id: string) => {
    if (!onDelete) return;
    setDeletingId(id);
    try {
      await onDelete(id);
      setConfirmDeleteId(null);
    } finally {
      setDeletingId(null);
    }
  };

  const handleInspect = async (doc: DocumentItem) => {
    setInspectDoc(doc);
    setExtractedData(null);
    if (!onViewExtracted) return;

    setLoadingExtracted(true);
    try {
      const data = await onViewExtracted(doc.id);
      setExtractedData(data);
    } finally {
      setLoadingExtracted(false);
    }
  };

  const renderStatusBadge = (doc: DocumentItem) => {
    const isProcessing = processingIds[doc.id] || doc.status === "processing";

    if (isProcessing) {
      return (
        <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
          <Loader2 className="w-3 h-3 animate-spin text-amber-600" />
          Processing
        </span>
      );
    }

    switch (doc.status) {
      case "processed":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-50 text-emerald-700 border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            Processed
          </span>
        );
      case "failed":
        return (
          <span
            className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-medium bg-rose-50 text-rose-700 border border-rose-200"
            title={doc.metadata?.error || "Extraction failed"}
          >
            <AlertCircle className="w-3 h-3 text-rose-600" />
            Failed
          </span>
        );
      default:
        return (
          <Badge variant="secondary" size="sm">
            Uploaded
          </Badge>
        );
    }
  };

  return (
    <div className="bg-white border border-slate-200/90 rounded-2xl shadow-xs overflow-hidden">
      {/* Table Header Controls */}
      <div className="p-4 sm:p-5 border-b border-slate-100 flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
        <div className="relative flex-1 max-w-sm">
          <Search className="w-4 h-4 absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search documents by name, type, or status..."
            className="w-full pl-9 pr-3.5 py-2 text-xs bg-slate-50 border border-slate-200 rounded-lg placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-500"
          />
        </div>

        <div className="flex items-center gap-2">
          {onUploadClick && (
            <Button
              variant="primary"
              size="sm"
              icon={<Upload className="w-3.5 h-3.5" />}
              onClick={onUploadClick}
            >
              Upload Document
            </Button>
          )}
        </div>
      </div>

      {/* Loading Skeleton */}
      {isLoading ? (
        <div className="p-12 text-center">
          <Loader2 className="w-8 h-8 animate-spin text-indigo-600 mx-auto mb-2" />
          <p className="text-xs text-slate-500">Loading documents from PostgreSQL...</p>
        </div>
      ) : documents.length === 0 ? (
        /* Genuine Empty State: No Documents */
        <div className="p-8 sm:p-12">
          <EmptyState
            icon={<FileText className="w-6 h-6 text-slate-400" />}
            title="No documents yet"
            description="Upload your first document to start asking Cogniva questions. Supported formats include PDF (.pdf) and Word (.docx)."
            action={
              onUploadClick ? (
                <Button
                  variant="outline"
                  size="sm"
                  icon={<Upload className="w-3.5 h-3.5" />}
                  onClick={onUploadClick}
                >
                  Upload Document
                </Button>
              ) : undefined
            }
          />
        </div>
      ) : filteredDocs.length === 0 ? (
        /* Search Query Has No Matches */
        <div className="p-8 sm:p-12 text-center">
          <p className="text-sm font-medium text-slate-700">No matching documents</p>
          <p className="text-xs text-slate-400 mt-1">
            No documents matched your search query &ldquo;{searchTerm}&rdquo;.
          </p>
        </div>
      ) : (
        /* Real Document Table */
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-slate-100 bg-slate-50 text-slate-500 font-medium">
                <th className="py-3 px-4">Document Name</th>
                <th className="py-3 px-4">Format</th>
                <th className="py-3 px-4">Size</th>
                <th className="py-3 px-4">Status</th>
                <th className="py-3 px-4">Extraction Details</th>
                <th className="py-3 px-4">Uploaded</th>
                <th className="py-3 px-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filteredDocs.map((doc) => {
                const isPdf = doc.file_type.toLowerCase() === "pdf";
                const isConfirming = confirmDeleteId === doc.id;
                const isDeleting = deletingId === doc.id;
                const isProcessing = processingIds[doc.id] || doc.status === "processing";

                return (
                  <tr
                    key={doc.id}
                    className="hover:bg-slate-50/70 transition-colors group"
                  >
                    <td className="py-3.5 px-4 font-medium text-slate-900">
                      <div className="flex items-center gap-2.5 max-w-xs sm:max-w-sm truncate">
                        <div
                          className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${
                            isPdf
                              ? "bg-rose-50 text-rose-600 border border-rose-100"
                              : "bg-blue-50 text-blue-600 border border-blue-100"
                          }`}
                        >
                          <FileText className="w-4 h-4" />
                        </div>
                        <div className="truncate">
                          <p className="text-xs font-medium text-slate-900 truncate">
                            {doc.original_filename || doc.filename}
                          </p>
                          <p className="text-[10px] text-slate-400 font-mono truncate">
                            ID: {doc.id.slice(0, 8)}...
                          </p>
                        </div>
                      </div>
                    </td>

                    <td className="py-3.5 px-4">
                      <Badge variant={isPdf ? "danger" : "info"} size="sm">
                        {doc.file_type.toUpperCase()}
                      </Badge>
                    </td>

                    <td className="py-3.5 px-4 text-slate-500 font-medium">
                      <div className="flex items-center gap-1.5 text-slate-500">
                        <HardDrive className="w-3 h-3 text-slate-400" />
                        <span>{formatFileSize(doc.metadata?.size_bytes)}</span>
                      </div>
                    </td>

                    <td className="py-3.5 px-4 whitespace-nowrap">
                      {renderStatusBadge(doc)}
                    </td>

                    {/* Extraction Details column */}
                    <td className="py-3.5 px-4 text-slate-600">
                      {doc.status === "processed" ? (
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-slate-800">
                            {doc.metadata?.total_pages
                              ? `${doc.metadata.total_pages} pages`
                              : `${doc.metadata?.total_units || 0} units`}
                          </span>
                          <span className="text-slate-400">•</span>
                          <span className="text-slate-500">
                            {doc.metadata?.total_words?.toLocaleString() || 0} words
                          </span>
                        </div>
                      ) : doc.status === "failed" ? (
                        <span className="text-rose-600 font-medium truncate max-w-[180px] inline-block">
                          {doc.metadata?.error || "Extraction error"}
                        </span>
                      ) : (
                        <span className="text-slate-400 italic">Pending extraction</span>
                      )}
                    </td>

                    <td className="py-3.5 px-4 text-slate-500 whitespace-nowrap">
                      <div className="flex items-center gap-1.5 text-slate-500">
                        <Calendar className="w-3 h-3 text-slate-400" />
                        <span>{formatDate(doc.created_at)}</span>
                      </div>
                    </td>

                    <td className="py-3.5 px-4 text-right whitespace-nowrap">
                      <div className="inline-flex items-center justify-end gap-1.5">
                        {/* Process / Extract button if uploaded or failed */}
                        {(doc.status === "uploaded" || doc.status === "failed") && onProcess && (
                          <button
                            onClick={() => onProcess(doc.id)}
                            disabled={isProcessing}
                            className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium rounded-lg bg-indigo-50 text-indigo-700 hover:bg-indigo-100 disabled:opacity-50 transition-colors"
                            title="Extract text content"
                          >
                            <Cpu className="w-3 h-3 text-indigo-600" />
                            <span>{doc.status === "failed" ? "Retry" : "Extract"}</span>
                          </button>
                        )}

                        {/* View Extracted Content button if processed */}
                        {doc.status === "processed" && onViewExtracted && (
                          <button
                            onClick={() => handleInspect(doc)}
                            className="inline-flex items-center gap-1 px-2.5 py-1 text-[11px] font-medium rounded-lg bg-slate-100 text-slate-700 hover:bg-slate-200 transition-colors"
                            title="Inspect extracted page text"
                          >
                            <Eye className="w-3 h-3 text-slate-600" />
                            <span>View Text</span>
                          </button>
                        )}

                        {/* Delete Action */}
                        {isConfirming ? (
                          <div className="inline-flex items-center gap-1 animate-in fade-in">
                            <button
                              onClick={() => handleDelete(doc.id)}
                              disabled={isDeleting}
                              className="px-2 py-1 text-[11px] font-medium rounded-md bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-50"
                            >
                              {isDeleting ? "..." : "Confirm"}
                            </button>
                            <button
                              onClick={() => setConfirmDeleteId(null)}
                              disabled={isDeleting}
                              className="px-2 py-1 text-[11px] font-medium rounded-md bg-slate-100 text-slate-600 hover:bg-slate-200"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setConfirmDeleteId(doc.id)}
                            className="p-1.5 rounded-lg text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-colors"
                            title="Delete document"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Extracted Content Inspection Modal */}
      {inspectDoc && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs animate-in fade-in">
          <div className="bg-white border border-slate-200 rounded-2xl shadow-xl max-w-2xl w-full max-h-[85vh] flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="p-4 sm:p-5 border-b border-slate-100 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
                  <Layers className="w-4 h-4" />
                </div>
                <div>
                  <h3 className="text-sm font-semibold text-slate-900">
                    Extracted Text & Provenance
                  </h3>
                  <p className="text-xs text-slate-500">
                    {inspectDoc.original_filename || inspectDoc.filename}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setInspectDoc(null)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-4 sm:p-6 overflow-y-auto space-y-4 flex-1">
              {loadingExtracted ? (
                <div className="py-12 text-center">
                  <Loader2 className="w-6 h-6 animate-spin text-indigo-600 mx-auto mb-2" />
                  <p className="text-xs text-slate-500">Loading structured document units...</p>
                </div>
              ) : extractedData && extractedData.units.length > 0 ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between text-xs text-slate-500 bg-slate-50 p-3 rounded-xl border border-slate-100">
                    <span>
                      <strong>Format:</strong> {extractedData.file_type.toUpperCase()}
                    </span>
                    <span>
                      <strong>Units:</strong> {extractedData.total_units}
                    </span>
                    <span>
                      <strong>Words:</strong> {extractedData.total_words.toLocaleString()}
                    </span>
                    {extractedData.total_pages && (
                      <span>
                        <strong>Pages:</strong> {extractedData.total_pages}
                      </span>
                    )}
                  </div>

                  <div className="space-y-3">
                    {extractedData.units.map((unit) => (
                      <div
                        key={unit.sequence_number}
                        className="p-3.5 rounded-xl border border-slate-200/80 bg-slate-50/50 hover:bg-white transition-colors"
                      >
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-[11px] font-semibold text-indigo-700 bg-indigo-50 px-2 py-0.5 rounded-md border border-indigo-100">
                            {unit.page_number !== null
                              ? `Page ${unit.page_number}`
                              : `Unit #${unit.sequence_number} (${unit.unit_type})`}
                          </span>
                          <span className="text-[10px] text-slate-400 font-mono">
                            Seq {unit.sequence_number}
                          </span>
                        </div>
                        <p className="text-xs text-slate-700 whitespace-pre-wrap leading-relaxed">
                          {unit.text}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="py-12 text-center text-xs text-slate-500">
                  No extracted content available for this document.
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-4 border-t border-slate-100 bg-slate-50 flex justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setInspectDoc(null)}
              >
                Close
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default DocumentTable;
