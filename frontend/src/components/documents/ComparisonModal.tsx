import React, { useState } from "react";
import { X, GitCompare, RefreshCw, CheckCircle2, AlertCircle, Copy, Check, FileText } from "lucide-react";
import Button from "../common/Button";
import Badge from "../common/Badge";
import Input from "../common/Input";
import { DocumentItem } from "../../types/document";
import { DocumentComparisonResponse } from "../../types/intelligence";
import { intelligenceService } from "../../services/intelligenceService";

interface ComparisonModalProps {
  documents: DocumentItem[];
  onClose: () => void;
}

export const ComparisonModal: React.FC<ComparisonModalProps> = ({ documents, onClose }) => {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<DocumentComparisonResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleCompare = async () => {
    if (documents.length < 2) return;
    setLoading(true);
    setError(null);
    try {
      const docIds = documents.map((d) => d.id);
      const res = await intelligenceService.compareDocuments(docIds, prompt.trim() || undefined);
      setResult(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to compare documents.");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (!result) return;
    navigator.clipboard.writeText(result.synthesis);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div className="bg-surface border border-border rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="p-4 border-b border-border flex items-center justify-between bg-panel/40">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded bg-accent/15 border border-accent/25 flex items-center justify-center text-accent">
              <GitCompare className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-primary">Multi-Document Comparative Analysis</h3>
              <p className="text-xs text-secondary">
                Comparing {documents.length} authorized documents side-by-side
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-secondary hover:text-primary hover:bg-canvas transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Selected Documents Ribbon */}
        <div className="px-4 py-2 bg-canvas/60 border-b border-border flex items-center gap-2 overflow-x-auto text-xs">
          <span className="text-secondary shrink-0 font-medium">Selected Assets:</span>
          {documents.map((d) => (
            <span
              key={d.id}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-panel border border-border text-primary font-medium shrink-0"
            >
              <FileText className="w-3 h-3 text-accent" />
              <span className="truncate max-w-[150px]">{d.original_filename || d.filename}</span>
            </span>
          ))}
        </div>

        {/* Query Input Section */}
        <div className="p-4 border-b border-border bg-panel/20 space-y-3">
          <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2">
            <input
              type="text"
              placeholder="Focus area (e.g. Compare pricing models, deliverables, SLAs, or termination clauses)..."
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              className="flex-1 text-xs px-3 py-2 rounded bg-surface border border-border text-primary placeholder:text-secondary/60 focus:outline-none focus:ring-1 focus:ring-accent"
            />
            <Button
              variant="primary"
              size="sm"
              onClick={handleCompare}
              disabled={loading}
              className="shrink-0 text-xs flex items-center justify-center gap-1.5"
            >
              {loading ? (
                <>
                  <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                  Analyzing...
                </>
              ) : (
                <>
                  <GitCompare className="w-3.5 h-3.5" />
                  Execute Comparison
                </>
              )}
            </Button>
          </div>
        </div>

        {/* Synthesis Results Body */}
        <div className="p-5 overflow-y-auto space-y-5 flex-1">
          {loading ? (
            <div className="py-16 flex flex-col items-center justify-center text-center space-y-3">
              <RefreshCw className="w-7 h-7 text-accent animate-spin" />
              <p className="text-xs text-secondary max-w-sm">
                Retrieving aligned passages across all {documents.length} documents and constructing cross-evidence synthesis...
              </p>
            </div>
          ) : error ? (
            <div className="p-3.5 rounded bg-red-500/10 border border-red-500/20 text-xs text-red-600 dark:text-red-400">
              {error}
            </div>
          ) : result ? (
            <div className="space-y-5">
              {/* Main Synthesis */}
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-primary uppercase tracking-wider">
                  Comparative Synthesis
                </h4>
                <div className="text-xs leading-relaxed text-secondary bg-panel/30 border border-border/60 rounded-lg p-4 whitespace-pre-line">
                  {result.synthesis}
                </div>
              </div>

              {/* Source Evidence Citations */}
              {result.sources && result.sources.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-primary uppercase tracking-wider">
                    Grounded Source Evidence ({result.sources.length})
                  </h4>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5">
                    {result.sources.map((src, idx) => (
                      <div
                        key={idx}
                        className="p-3 rounded border border-border/70 bg-surface/60 text-xs space-y-1.5"
                      >
                        <div className="flex items-center justify-between text-[11px] font-medium text-primary">
                          <span className="truncate max-w-[200px] text-accent">
                            {src.filename}
                          </span>
                          <span className="text-secondary font-mono">
                            Page {src.page_number || "N/A"}
                          </span>
                        </div>
                        <p className="text-secondary/90 text-[11px] leading-relaxed line-clamp-3">
                          {src.excerpt}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="py-12 text-center text-xs text-secondary">
              Select or type a focus area above, then click "Execute Comparison" to generate cross-document findings.
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-border bg-panel/40 flex items-center justify-between">
          <Button
            variant="outline"
            size="sm"
            onClick={handleCopy}
            disabled={!result || loading}
            className="text-xs flex items-center gap-1.5"
          >
            {copied ? (
              <>
                <Check className="w-3.5 h-3.5 text-emerald-500" />
                Copied
              </>
            ) : (
              <>
                <Copy className="w-3.5 h-3.5" />
                Copy Synthesis
              </>
            )}
          </Button>

          <Button variant="secondary" size="sm" onClick={onClose} className="text-xs">
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ComparisonModal;
