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
  Copy,
  Check,
  Sparkles,
  Table,
  GitCompare,
  FolderPlus,
  BookOpen,
  Download,
} from "lucide-react";
import Button from "../common/Button";
import EmptyState from "../common/EmptyState";
import Badge from "../common/Badge";
import { DocumentItem, ExtractedDocument, DocumentJob } from "../../types/document";
import { documentService } from "../../services/documentService";
import SummaryModal from "./SummaryModal";
import StructuredExtractModal from "./StructuredExtractModal";
import ComparisonModal from "./ComparisonModal";
import ReportModal from "./ReportModal";
import CollectionModal from "./CollectionModal";
import DocumentViewerModal from "./DocumentViewerModal";

interface DocumentTableProps {
  documents: DocumentItem[];
  isLoading?: boolean;
  processingIds?: Record<string, boolean>;
  jobStates?: Record<string, DocumentJob>;
  onDelete?: (id: string) => Promise<boolean | unknown>;
  onProcess?: (id: string) => Promise<unknown>;
  onViewExtracted?: (id: string) => Promise<ExtractedDocument | null>;
  onUploadClick?: () => void;
  initialViewerDocId?: string | null;
}

export const DocumentTable: React.FC<DocumentTableProps> = ({
  documents = [],
  isLoading = false,
  processingIds = {},
  jobStates = {},
  onDelete,
  onProcess,
  onViewExtracted,
  onUploadClick,
  initialViewerDocId,
}) => {
  const [searchTerm, setSearchTerm] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);

  const handleDownload = async (doc: DocumentItem) => {
    setDownloadingId(doc.id);
    try {
      await documentService.downloadDocument(doc.id, doc.original_filename || doc.filename);
    } catch (err) {
      console.error("Failed to download document:", err);
    } finally {
      setDownloadingId(null);
    }
  };

  // Multi-selection state
  const [selectedDocIds, setSelectedDocIds] = useState<string[]>([]);

  // Modals state
  const [viewerDoc, setViewerDoc] = useState<DocumentItem | null>(null);
  const [summarizeDoc, setSummarizeDoc] = useState<DocumentItem | null>(null);
  const [extractDoc, setExtractDoc] = useState<DocumentItem | null>(null);
  const [isComparing, setIsComparing] = useState(false);
  const [isGeneratingReport, setIsGeneratingReport] = useState(false);
  const [collectionDocId, setCollectionDocId] = useState<string | null>(null);

  // Sync initial viewer doc if passed from route or parent
  React.useEffect(() => {
    if (initialViewerDocId && documents.length > 0) {
      const match = documents.find((d) => d.id === initialViewerDocId);
      if (match) {
        setViewerDoc(match);
      }
    }
  }, [initialViewerDocId, documents]);

  // Modal inspection state for extracted text
  const [inspectDoc, setInspectDoc] = useState<DocumentItem | null>(null);
  const [extractedData, setExtractedData] = useState<ExtractedDocument | null>(null);
  const [loadingExtracted, setLoadingExtracted] = useState(false);
  const [copiedUnit, setCopiedUnit] = useState<number | null>(null);

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
      setSelectedDocIds((prev) => prev.filter((dId) => dId !== id));
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

  const handleCopyUnit = (seq: number, text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedUnit(seq);
    setTimeout(() => setCopiedUnit(null), 2000);
  };

  const toggleSelectDoc = (id: string) => {
    setSelectedDocIds((prev) =>
      prev.includes(id) ? prev.filter((dId) => dId !== id) : [...prev, id]
    );
  };

  const toggleSelectAll = () => {
    const processedIds = filteredDocs
      .filter((d) => d.status === "processed")
      .map((d) => d.id);
    if (selectedDocIds.length === processedIds.length) {
      setSelectedDocIds([]);
    } else {
      setSelectedDocIds(processedIds);
    }
  };

  const selectedDocuments = documents.filter((d) => selectedDocIds.includes(d.id));

  const renderStatusBadge = (doc: DocumentItem) => {
    const isProcessing = processingIds[doc.id] || doc.status === "processing";
    const job = jobStates[doc.id];

    if (isProcessing) {
      if (job?.is_stuck) {
        return (
          <span
            className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium bg-amber-200/80 dark:bg-amber-900/50 text-amber-950 dark:text-amber-200 border border-amber-400 dark:border-amber-700 animate-pulse"
            title={job?.diagnosis || "Pipeline appears stuck. Re-queue via retry."}
          >
            <AlertCircle className="w-3 h-3 text-amber-700 dark:text-amber-300" />
            Stuck ({job?.stage || "pipeline"})
          </span>
        );
      }

      const stageLabel = job?.stage
        ? job.stage.charAt(0).toUpperCase() + job.stage.slice(1)
        : "Processing";
      const progressLabel = job?.progress !== undefined && job.progress > 0 ? ` (${job.progress}%)` : "";

      return (
        <span
          className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium bg-amber-100/70 dark:bg-amber-950/40 text-amber-900 dark:text-amber-300 border border-amber-300 dark:border-amber-800"
          title={job?.error_message ? `Attempt ${job.retry_count}: ${job.error_message}` : `Current stage: ${stageLabel}`}
        >
          <Loader2 className="w-3 h-3 animate-spin text-amber-600" />
          {stageLabel}{progressLabel}
        </span>
      );
    }

    switch (doc.status) {
      case "processed":
        return (
          <span
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-emerald-100/70 dark:bg-emerald-950/40 text-emerald-900 dark:text-emerald-300 border border-emerald-300 dark:border-emerald-800"
            title={job?.duration_seconds ? `Processing completed in ${job.duration_seconds}s` : undefined}
          >
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            Processed
            {job?.duration_seconds ? (
              <span className="text-[10px] opacity-75 font-mono">({job.duration_seconds}s)</span>
            ) : null}
          </span>
        );
      case "failed":
        if (job?.retries_exhausted) {
          return (
            <span
              className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-rose-200/80 dark:bg-rose-950/60 text-rose-950 dark:text-rose-200 border border-rose-400 dark:border-rose-700"
              title={job?.diagnosis || job?.error_message || "Retry limit reached"}
            >
              <AlertCircle className="w-3 h-3 text-rose-600" />
              Retries Exhausted
            </span>
          );
        }
        return (
          <span
            className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-[11px] font-medium bg-rose-100/70 dark:bg-rose-950/40 text-rose-900 dark:text-rose-300 border border-rose-300 dark:border-rose-800"
            title={job?.diagnosis || job?.error_message || doc.metadata?.error || "Processing failed"}
          >
            <AlertCircle className="w-3 h-3 text-rose-600" />
            Failed
          </span>
        );
      default:
        return (
          <Badge variant="secondary" size="xs">
            Uploaded
          </Badge>
        );
    }
  };

  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden transition-colors">
      {/* Table Header Controls */}
      <div className="p-3.5 sm:p-4 border-b border-border flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between bg-panel/30">
        <div className="relative flex-1 max-w-sm">
          <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-secondary pointer-events-none" />
          <input
            type="text"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            placeholder="Search documents by name, type, or status..."
            className="w-full pl-8 pr-3 py-1.5 text-xs bg-surface border border-border rounded-lg text-primary placeholder:text-secondary/70 focus:outline-none focus:border-accent"
          />
        </div>

        <div className="flex items-center gap-2">
          {onUploadClick && (
            <Button
              variant="primary"
              size="xs"
              icon={<Upload className="w-3.5 h-3.5" />}
              onClick={onUploadClick}
            >
              Upload Document
            </Button>
          )}
        </div>
      </div>

      {/* Multi-Selection Action Ribbon */}
      {selectedDocIds.length > 0 && (
        <div className="px-4 py-2 bg-accent/10 border-b border-accent/20 flex items-center justify-between flex-wrap gap-2 text-xs animate-in fade-in">
          <span className="font-medium text-primary">
            {selectedDocIds.length} {selectedDocIds.length === 1 ? "document" : "documents"} selected
          </span>
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="xs"
              onClick={() => setIsComparing(true)}
              disabled={selectedDocIds.length < 2 || selectedDocIds.length > 5}
              className="text-[11px] h-6.5 flex items-center gap-1"
              title={selectedDocIds.length < 2 ? "Select at least 2 documents" : undefined}
            >
              <GitCompare className="w-3 h-3 text-accent" />
              Compare ({selectedDocIds.length})
            </Button>
            <Button
              variant="outline"
              size="xs"
              onClick={() => setIsGeneratingReport(true)}
              className="text-[11px] h-6.5 flex items-center gap-1"
            >
              <FileText className="w-3 h-3 text-accent" />
              Generate Report
            </Button>
            <button
              onClick={() => setSelectedDocIds([])}
              className="text-[11px] text-secondary hover:text-primary transition-colors ml-1 cursor-pointer"
            >
              Deselect All
            </button>
          </div>
        </div>
      )}

      {/* Loading Skeleton */}
      {isLoading ? (
        <div className="p-12 text-center text-secondary">
          <Loader2 className="w-6 h-6 animate-spin text-accent mx-auto mb-2" />
          <p className="text-xs">Loading documents from PostgreSQL repository...</p>
        </div>
      ) : documents.length === 0 ? (
        /* Genuine Empty State: No Documents */
        <div className="p-8 sm:p-12">
          <EmptyState
            icon={<FileText className="w-6 h-6 text-secondary" />}
            title="Knowledge repository is empty"
            description="Upload enterprise documentation (PDF, Word, or CSV) to generate structural vector chunks with page provenance."
            action={
              onUploadClick ? (
                <Button
                  variant="outline"
                  size="xs"
                  icon={<Upload className="w-3.5 h-3.5" />}
                  onClick={onUploadClick}
                >
                  Upload First Document
                </Button>
              ) : undefined
            }
          />
        </div>
      ) : filteredDocs.length === 0 ? (
        /* Search Query Has No Matches */
        <div className="p-8 sm:p-12 text-center">
          <p className="text-xs sm:text-sm font-medium text-primary">No matching knowledge assets</p>
          <p className="text-xs text-secondary mt-1">
            No documents matched &ldquo;{searchTerm}&rdquo;. Try another search term.
          </p>
        </div>
      ) : (
        /* Real Document Table */
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-xs">
            <thead>
              <tr className="border-b border-border bg-panel/50 text-secondary font-medium">
                <th className="py-2.5 px-3 w-8 text-center">
                  <input
                    type="checkbox"
                    checked={
                      selectedDocIds.length > 0 &&
                      selectedDocIds.length ===
                        filteredDocs.filter((d) => d.status === "processed").length
                    }
                    onChange={toggleSelectAll}
                    className="rounded border-border text-accent focus:ring-accent cursor-pointer"
                  />
                </th>
                <th className="py-2.5 px-3">Document Asset</th>
                <th className="py-2.5 px-3">Format</th>
                <th className="py-2.5 px-3">Size</th>
                <th className="py-2.5 px-3">Status</th>
                <th className="py-2.5 px-3">Indexing Details</th>
                <th className="py-2.5 px-3">Ingested</th>
                <th className="py-2.5 px-3 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {filteredDocs.map((doc) => {
                const isConfirming = confirmDeleteId === doc.id;
                const isDeleting = deletingId === doc.id;
                const isProcessing = processingIds[doc.id] || doc.status === "processing";
                const isSelected = selectedDocIds.includes(doc.id);

                return (
                  <tr
                    key={doc.id}
                    className={`hover:bg-panel/40 transition-colors group ${
                      isSelected ? "bg-accent/5" : ""
                    }`}
                  >
                    <td className="py-3 px-3 text-center">
                      <input
                        type="checkbox"
                        checked={isSelected}
                        disabled={doc.status !== "processed"}
                        onChange={() => toggleSelectDoc(doc.id)}
                        className="rounded border-border text-accent focus:ring-accent cursor-pointer disabled:opacity-40"
                      />
                    </td>

                    <td className="py-3 px-3 font-medium text-primary">
                      <div className="flex items-center gap-2 max-w-xs sm:max-w-sm truncate">
                        <div className="w-7 h-7 rounded bg-panel border border-border flex items-center justify-center shrink-0 text-secondary">
                          <FileText className="w-3.5 h-3.5" />
                        </div>
                        <div className="truncate">
                          <button
                            type="button"
                            onClick={() => setViewerDoc(doc)}
                            className="text-xs font-semibold text-primary hover:text-accent truncate block text-left transition-colors cursor-pointer"
                            title="Open Document Viewer (Insights, Takeaways, Citations & Questions)"
                          >
                            {doc.original_filename || doc.filename}
                          </button>
                          <p className="text-[10px] text-secondary font-mono truncate">
                            UUID: {doc.id.slice(0, 8)}...
                          </p>
                        </div>
                      </div>
                    </td>

                    <td className="py-3 px-3">
                      <Badge variant="neutral" size="xs">
                        {doc.file_type.toUpperCase()}
                      </Badge>
                    </td>

                    <td className="py-3 px-3 text-secondary font-mono">
                      <div className="flex items-center gap-1.5">
                        <HardDrive className="w-3 h-3 text-secondary" />
                        <span>{formatFileSize(doc.metadata?.size_bytes)}</span>
                      </div>
                    </td>

                    <td className="py-3 px-3 whitespace-nowrap">
                      {renderStatusBadge(doc)}
                    </td>

                    {/* Extraction Details column */}
                    <td className="py-3 px-3 text-secondary">
                      {doc.status === "processed" ? (
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-primary">
                            {doc.metadata?.total_pages
                              ? `${doc.metadata.total_pages} pages`
                              : `${doc.metadata?.total_units || 0} units`}
                          </span>
                          <span>•</span>
                          <span className="font-mono">
                            {doc.metadata?.total_words?.toLocaleString() || 0} words
                          </span>
                        </div>
                      ) : doc.status === "failed" ? (
                        <span className="text-rose-600 dark:text-rose-400 font-medium truncate max-w-[180px] inline-block">
                          {doc.metadata?.error || "Pipeline error"}
                        </span>
                      ) : (
                        <span className="text-secondary italic">Pending extraction</span>
                      )}
                    </td>

                    <td className="py-3 px-3 text-secondary whitespace-nowrap font-mono text-[11px]">
                      <div className="flex items-center gap-1.5">
                        <Calendar className="w-3 h-3 text-secondary" />
                        <span>{formatDate(doc.created_at)}</span>
                      </div>
                    </td>

                    <td className="py-3 px-3 text-right whitespace-nowrap">
                      <div className="inline-flex items-center justify-end gap-1">
                        {/* Process / Extract button if uploaded or failed */}
                        {(doc.status === "uploaded" || doc.status === "failed") && onProcess && (
                          <button
                            onClick={() => onProcess(doc.id)}
                            disabled={isProcessing}
                            className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-medium rounded border border-border bg-panel hover:bg-panel/80 text-primary disabled:opacity-50 transition-colors cursor-pointer"
                            title="Execute parsing and embedding"
                          >
                            <Cpu className="w-3 h-3 text-accent" />
                            <span>{doc.status === "failed" ? "Retry" : "Process"}</span>
                          </button>
                        )}

                        {/* Document Viewer action */}
                        <button
                          type="button"
                          onClick={() => setViewerDoc(doc)}
                          className="p-1.5 rounded border border-border bg-surface hover:bg-panel text-accent transition-colors cursor-pointer"
                          title="Open Document Viewer (Insights, Takeaways, Citations & Questions)"
                        >
                          <BookOpen className="w-3.5 h-3.5" />
                        </button>

                        {/* Intelligence Actions (Summary, Extract, Collection) */}
                        {doc.status === "processed" && (
                          <>
                            <button
                              onClick={() => setSummarizeDoc(doc)}
                              className="p-1.5 rounded border border-border bg-surface hover:bg-panel text-primary transition-colors cursor-pointer"
                              title="Executive Document Summary"
                            >
                              <Sparkles className="w-3.5 h-3.5 text-accent" />
                            </button>
                            <button
                              onClick={() => setExtractDoc(doc)}
                              className="p-1.5 rounded border border-border bg-surface hover:bg-panel text-primary transition-colors cursor-pointer"
                              title="Extract Structured Data & CSV"
                            >
                              <Table className="w-3.5 h-3.5 text-secondary" />
                            </button>
                            <button
                              onClick={() => setCollectionDocId(doc.id)}
                              className="p-1.5 rounded border border-border bg-surface hover:bg-panel text-primary transition-colors cursor-pointer"
                              title="Assign to Collection"
                            >
                              <FolderPlus className="w-3.5 h-3.5 text-secondary" />
                            </button>
                            {onViewExtracted && (
                              <button
                                onClick={() => handleInspect(doc)}
                                className="p-1.5 rounded border border-border bg-surface hover:bg-panel text-primary transition-colors cursor-pointer"
                                title="Inspect extracted structured units"
                              >
                                <Eye className="w-3.5 h-3.5 text-secondary" />
                              </button>
                            )}
                            <button
                              onClick={() => handleDownload(doc)}
                              disabled={downloadingId === doc.id}
                              className="p-1.5 rounded border border-border bg-surface hover:bg-panel text-primary transition-colors cursor-pointer"
                              title="Download authentic original binary"
                            >
                              {downloadingId === doc.id ? (
                                <Loader2 className="w-3.5 h-3.5 animate-spin text-accent" />
                              ) : (
                                <Download className="w-3.5 h-3.5 text-secondary" />
                              )}
                            </button>
                          </>
                        )}

                        {/* Delete Action with inline confirm */}
                        {isConfirming ? (
                          <div className="inline-flex items-center gap-1 bg-surface border border-border rounded p-0.5 ml-1">
                            <button
                              onClick={() => handleDelete(doc.id)}
                              disabled={isDeleting}
                              className="px-2 py-0.5 text-[10px] font-medium rounded bg-rose-700 text-white hover:bg-rose-800 disabled:opacity-50 cursor-pointer"
                            >
                              {isDeleting ? "..." : "Delete"}
                            </button>
                            <button
                              onClick={() => setConfirmDeleteId(null)}
                              disabled={isDeleting}
                              className="px-1.5 py-0.5 text-[10px] font-medium rounded bg-panel text-secondary hover:text-primary cursor-pointer"
                            >
                              Cancel
                            </button>
                          </div>
                        ) : (
                          <button
                            onClick={() => setConfirmDeleteId(doc.id)}
                            className="p-1.5 rounded text-secondary hover:text-rose-600 hover:bg-panel transition-colors cursor-pointer ml-1"
                            title="Safe delete document"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
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
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
          <div className="bg-surface border border-border rounded-xl shadow-xl max-w-2xl w-full max-h-[85vh] flex flex-col overflow-hidden text-primary">
            <div className="p-4 border-b border-border flex items-center justify-between bg-panel/40">
              <div className="flex items-center gap-2.5 min-w-0">
                <div className="w-7 h-7 rounded bg-panel border border-border flex items-center justify-center text-accent shrink-0">
                  <Layers className="w-4 h-4" />
                </div>
                <div className="min-w-0">
                  <h3 className="text-xs sm:text-sm font-semibold text-primary truncate">
                    Structured Ingestion Units & Provenance
                  </h3>
                  <p className="text-[10px] text-secondary truncate">
                    {inspectDoc.original_filename || inspectDoc.filename}
                  </p>
                </div>
              </div>
              <button
                onClick={() => setInspectDoc(null)}
                className="p-1 rounded text-secondary hover:text-primary hover:bg-panel cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="p-4 sm:p-5 overflow-y-auto space-y-3 flex-1">
              {loadingExtracted ? (
                <div className="py-12 text-center text-secondary">
                  <Loader2 className="w-5 h-5 animate-spin text-accent mx-auto mb-2" />
                  <p className="text-xs">Loading structured document units...</p>
                </div>
              ) : extractedData && extractedData.units.length > 0 ? (
                <div className="space-y-3">
                  <div className="flex items-center justify-between text-xs text-secondary bg-panel/50 p-2.5 rounded-lg border border-border font-mono text-[11px]">
                    <span>
                      Format: <strong className="text-primary">{extractedData.file_type.toUpperCase()}</strong>
                    </span>
                    <span>
                      Units: <strong className="text-primary">{extractedData.total_units}</strong>
                    </span>
                    <span>
                      Words: <strong className="text-primary">{extractedData.total_words.toLocaleString()}</strong>
                    </span>
                    {extractedData.total_pages && (
                      <span>
                        Pages: <strong className="text-primary">{extractedData.total_pages}</strong>
                      </span>
                    )}
                  </div>

                  <div className="space-y-2.5">
                    {extractedData.units.map((unit) => (
                      <div
                        key={unit.sequence_number}
                        className="p-3 rounded-lg border border-border bg-panel/30 hover:bg-panel/60 transition-colors"
                      >
                        <div className="flex items-center justify-between mb-1.5">
                          <span className="text-[10px] font-semibold text-accent bg-panel px-2 py-0.5 rounded border border-border font-mono">
                            {unit.page_number !== null
                              ? `Page ${unit.page_number}`
                              : `Unit #${unit.sequence_number} (${unit.unit_type})`}
                          </span>
                          <div className="flex items-center gap-2">
                            <span className="text-[10px] text-secondary font-mono">
                              Seq {unit.sequence_number}
                            </span>
                            <button
                              onClick={() => handleCopyUnit(unit.sequence_number, unit.text)}
                              className="p-1 rounded text-secondary hover:text-primary hover:bg-panel transition-colors cursor-pointer"
                              title="Copy unit text"
                            >
                              {copiedUnit === unit.sequence_number ? (
                                <Check className="w-3 h-3 text-accent" />
                              ) : (
                                <Copy className="w-3 h-3" />
                              )}
                            </button>
                          </div>
                        </div>
                        <p className="text-xs text-primary whitespace-pre-wrap leading-relaxed font-sans">
                          {unit.text}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="py-12 text-center text-xs text-secondary">
                  No extracted content available for this document.
                </div>
              )}
            </div>

            <div className="p-3 border-t border-border bg-panel/30 flex justify-end">
              <Button
                variant="outline"
                size="xs"
                onClick={() => setInspectDoc(null)}
              >
                Close
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Standalone Document Viewer */}
      {viewerDoc && (
        <DocumentViewerModal
          document={viewerDoc}
          onClose={() => setViewerDoc(null)}
          onProcess={onProcess}
        />
      )}

      {/* Intelligence Modals */}
      {summarizeDoc && (
        <SummaryModal
          document={summarizeDoc}
          onClose={() => setSummarizeDoc(null)}
        />
      )}

      {extractDoc && (
        <StructuredExtractModal
          document={extractDoc}
          onClose={() => setExtractDoc(null)}
        />
      )}

      {isComparing && (
        <ComparisonModal
          documents={selectedDocuments}
          onClose={() => setIsComparing(false)}
        />
      )}

      {isGeneratingReport && (
        <ReportModal
          documents={documents}
          selectedDocumentIds={selectedDocIds}
          onClose={() => setIsGeneratingReport(false)}
        />
      )}

      {collectionDocId && (
        <CollectionModal
          assignDocumentId={collectionDocId}
          onClose={() => setCollectionDocId(null)}
        />
      )}
    </div>
  );
};

export default DocumentTable;
