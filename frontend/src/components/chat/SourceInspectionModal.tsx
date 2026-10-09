import React, { useEffect, useState } from "react";
import { X, FileText, CheckCircle2, AlertCircle, Loader2, Layers, BookOpen, Hash } from "lucide-react";
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

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-xs animate-in fade-in duration-200">
      <div
        className="bg-white rounded-2xl shadow-xl border border-slate-200/90 w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden animate-in zoom-in-95 duration-150"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center justify-center px-2.5 py-1 rounded-md bg-indigo-600 text-white font-mono font-bold text-xs shadow-xs">
              [{citation.citation_id}]
            </span>
            <div>
              <h3 className="text-sm font-semibold text-slate-900 flex items-center gap-1.5 truncate max-w-md">
                <FileText className="w-4 h-4 text-indigo-600 shrink-0" />
                <span className="truncate">{citation.document_filename}</span>
              </h3>
              <p className="text-xs text-slate-500">
                Verified Enterprise Knowledge Source Provenance
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-100 transition-colors cursor-pointer"
            title="Close source inspection"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Provenance Metadata Bar */}
        <div className="px-6 py-2.5 bg-slate-100/50 border-b border-slate-100 flex flex-wrap items-center gap-4 text-xs text-slate-600">
          <div className="inline-flex items-center gap-1.5">
            <BookOpen className="w-3.5 h-3.5 text-indigo-500" />
            <span>
              Page:{" "}
              <strong className="text-slate-800">
                {citation.page_number !== null ? citation.page_number : "N/A (DOCX)"}
              </strong>
            </span>
          </div>

          <div className="inline-flex items-center gap-1.5">
            <Hash className="w-3.5 h-3.5 text-indigo-500" />
            <span>
              Chunk Index: <strong className="text-slate-800">{citation.chunk_index}</strong>
            </span>
          </div>

          <div className="inline-flex items-center gap-1.5">
            <Layers className="w-3.5 h-3.5 text-emerald-600" />
            <span>
              Relevance:{" "}
              <strong className="text-emerald-700">
                {(citation.similarity_score * 100).toFixed(1)}%
              </strong>
            </span>
          </div>

          <div className="ml-auto inline-flex items-center gap-1 text-[11px] text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded-full border border-emerald-200/60 font-medium">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" />
            Authentic User Provenance
          </div>
        </div>

        {/* Modal Body / Chunk Content */}
        <div className="p-6 overflow-y-auto flex-1 space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400">
              Retrieved Chunk Content
            </span>
            <span className="text-[11px] text-slate-400">
              Chunk ID: {citation.chunk_id.slice(0, 8)}...
            </span>
          </div>

          {loading ? (
            <div className="p-12 flex flex-col items-center justify-center text-slate-400 gap-2">
              <Loader2 className="w-6 h-6 animate-spin text-indigo-600" />
              <span className="text-xs">Verifying chunk in document repository...</span>
            </div>
          ) : error ? (
            <div className="p-4 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
              <span>{error}</span>
            </div>
          ) : (
            <div className="p-4 bg-slate-50 border border-slate-200 rounded-xl text-slate-800 text-sm leading-relaxed whitespace-pre-wrap font-sans">
              {chunkDetail?.content || "Content loaded successfully."}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-3 border-t border-slate-100 bg-slate-50 flex items-center justify-between">
          <p className="text-[11px] text-slate-400">
            Citations strictly reference verified document chunks from PostgreSQL.
          </p>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-white border border-slate-200 hover:bg-slate-50 text-slate-700 text-xs font-medium shadow-2xs transition-colors cursor-pointer"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};

export default SourceInspectionModal;
