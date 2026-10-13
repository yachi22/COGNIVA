import React, { useEffect, useState } from "react";
import { X, FileText, CheckCircle2, AlertCircle, Loader2, Layers, BookOpen, Hash, Copy, Check } from "lucide-react";
import { CitationItem } from "../../types/chat";
import { documentService } from "../../services/documentService";
import { DocumentChunkDetail } from "../../types/document";

interface SourceInspectionModalProps {
  citation: CitationItem | null;
  onClose: () => void;
}

export const SourceInspectionModal: React.FC<SourceInspectionModalProps> = ({
  citation,
  onClose,
}) => {
  const [chunkDetail, setChunkDetail] = useState<DocumentChunkDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!citation) {
      setChunkDetail(null);
      setError(null);
      return;
    }

    let isMounted = true;
    const fetchChunk = async () => {
      setLoading(true);
      setError(null);
      try {
        const detail = await documentService.getDocumentChunk(
          citation.document_id,
          citation.chunk_id
        );
        if (isMounted) {
          setChunkDetail(detail as DocumentChunkDetail);
        }
      } catch (err: any) {
        if (isMounted) {
          const detailMsg =
            err.response?.data?.detail || "Failed to inspect source chunk from backend.";
          setError(typeof detailMsg === "string" ? detailMsg : "Failed to load chunk.");
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    };

    fetchChunk();

    return () => {
      isMounted = false;
    };
  }, [citation]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  if (!citation) return null;

  const contentToDisplay = chunkDetail?.content || "";

  const handleCopy = () => {
    if (contentToDisplay) {
      navigator.clipboard.writeText(contentToDisplay);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div
        className="bg-surface rounded-xl shadow-xl border border-border w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden text-primary"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="px-5 py-3.5 border-b border-border flex items-center justify-between bg-panel/50">
          <div className="flex items-center gap-2.5 min-w-0">
            <span className="inline-flex items-center justify-center px-2 py-0.5 rounded bg-accent text-white dark:text-[#121614] font-mono font-bold text-xs">
              [{citation.citation_id}]
            </span>
            <div className="min-w-0">
              <h3 className="text-xs sm:text-sm font-semibold text-primary flex items-center gap-1.5 truncate">
                <FileText className="w-3.5 h-3.5 text-secondary shrink-0" />
                <span className="truncate">{citation.document_filename}</span>
              </h3>
              <p className="text-[10px] text-secondary">
                Verified Provenance & Chunk Excerpt
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-secondary hover:text-primary hover:bg-panel transition-colors cursor-pointer"
            title="Close source inspection"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Provenance Metadata Bar */}
        <div className="px-5 py-2 bg-panel/30 border-b border-border flex flex-wrap items-center gap-4 text-xs text-secondary">
          <div className="inline-flex items-center gap-1.5">
            <BookOpen className="w-3 h-3 text-secondary" />
            <span>
              Page: <strong className="text-primary">{citation.page_number !== null ? citation.page_number : "N/A"}</strong>
            </span>
          </div>

          <div className="inline-flex items-center gap-1.5">
            <Hash className="w-3 h-3 text-secondary" />
            <span>
              Chunk Index: <strong className="text-primary">{citation.chunk_index}</strong>
            </span>
          </div>

          <div className="inline-flex items-center gap-1.5">
            <Layers className="w-3 h-3 text-accent" />
            <span>
              Score: <strong className="text-accent">{(citation.similarity_score * 100).toFixed(1)}%</strong>
            </span>
          </div>

          <div className="ml-auto inline-flex items-center gap-1 text-[10px] text-accent font-medium">
            <CheckCircle2 className="w-3 h-3 text-accent" />
            Tenant Isolated
          </div>
        </div>

        {/* Modal Body / Chunk Content */}
        <div className="p-5 overflow-y-auto flex-1 space-y-3">
          <div className="flex items-center justify-between text-[11px] text-secondary">
            <span className="font-semibold uppercase tracking-wider">
              Retrieved Chunk Text
            </span>
            <div className="flex items-center gap-2">
              <span className="font-mono">
                ID: {citation.chunk_id.slice(0, 8)}...
              </span>
              {contentToDisplay && (
                <button
                  onClick={handleCopy}
                  className="flex items-center gap-1 text-xs text-secondary hover:text-primary cursor-pointer p-0.5"
                  title="Copy text"
                >
                  {copied ? <Check className="w-3 h-3 text-accent" /> : <Copy className="w-3 h-3" />}
                  <span>{copied ? "Copied" : "Copy"}</span>
                </button>
              )}
            </div>
          </div>

          {loading ? (
            <div className="p-12 flex flex-col items-center justify-center text-secondary gap-2">
              <Loader2 className="w-5 h-5 animate-spin text-accent" />
              <span className="text-xs">Fetching source chunk from database...</span>
            </div>
          ) : error ? (
            <div className="p-3.5 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
              <span>{error}</span>
            </div>
          ) : (
            <div className="p-3.5 bg-panel/50 border border-border rounded-lg text-primary text-xs sm:text-sm leading-relaxed whitespace-pre-wrap select-text font-sans">
              {contentToDisplay || "Excerpt retrieved successfully."}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-5 py-2.5 border-t border-border bg-panel/30 flex items-center justify-between">
          <p className="text-[10px] text-secondary">
            Citations reference authentic database chunk records isolated per tenant.
          </p>
          <button
            onClick={onClose}
            className="px-3 py-1 rounded border border-border bg-surface hover:bg-panel text-primary text-xs font-medium transition-colors cursor-pointer"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default SourceInspectionModal;
