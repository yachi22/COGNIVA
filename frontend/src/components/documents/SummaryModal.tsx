import React, { useState, useEffect } from "react";
import { X, Sparkles, RefreshCw, FileText, CheckCircle2, Copy, Check } from "lucide-react";
import Button from "../common/Button";
import Badge from "../common/Badge";
import { DocumentItem } from "../../types/document";
import { DocumentSummaryResponse } from "../../types/intelligence";
import { intelligenceService } from "../../services/intelligenceService";

interface SummaryModalProps {
  document: DocumentItem | null;
  onClose: () => void;
}

export const SummaryModal: React.FC<SummaryModalProps> = ({ document, onClose }) => {
  const [mode, setMode] = useState<"concise" | "detailed">("concise");
  const [loading, setLoading] = useState(false);
  const [summaryData, setSummaryData] = useState<DocumentSummaryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (document) {
      loadSummary(false);
    } else {
      setSummaryData(null);
      setError(null);
    }
  }, [document, mode]);

  const loadSummary = async (forceRefresh: boolean = false) => {
    if (!document) return;
    setLoading(true);
    setError(null);
    try {
      const res = await intelligenceService.summarizeDocument(document.id, mode, forceRefresh);
      setSummaryData(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to generate document summary.");
    } finally {
      setLoading(false);
    }
  };

  const handleCopy = () => {
    if (!summaryData) return;
    const text = `# Summary: ${summaryData.document_filename}\n\n${summaryData.summary}\n\nKey Takeaways:\n${summaryData.key_takeaways.map((t) => `- ${t}`).join("\n")}`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!document) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div className="bg-surface border border-border rounded-lg shadow-xl w-full max-w-2xl max-h-[85vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="p-4 border-b border-border flex items-center justify-between bg-panel/40">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded bg-accent/15 border border-accent/25 flex items-center justify-center text-accent">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-primary">Executive Document Summary</h3>
              <p className="text-xs text-secondary truncate max-w-md">
                {document.original_filename || document.filename}
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

        {/* Controls Toolbar */}
        <div className="px-4 py-2.5 border-b border-border bg-canvas/40 flex items-center justify-between flex-wrap gap-2 text-xs">
          <div className="flex items-center gap-1.5 bg-panel p-0.5 rounded border border-border">
            <button
              onClick={() => setMode("concise")}
              className={`px-2.5 py-1 rounded font-medium transition-colors ${
                mode === "concise"
                  ? "bg-surface text-primary shadow-xs"
                  : "text-secondary hover:text-primary"
              }`}
            >
              Concise (Executive)
            </button>
            <button
              onClick={() => setMode("detailed")}
              className={`px-2.5 py-1 rounded font-medium transition-colors ${
                mode === "detailed"
                  ? "bg-surface text-primary shadow-xs"
                  : "text-secondary hover:text-primary"
              }`}
            >
              Detailed (Comprehensive)
            </button>
          </div>

          <div className="flex items-center gap-2">
            {summaryData?.cached && (
              <Badge variant="neutral" className="text-[10px]">
                Cached Result
              </Badge>
            )}
            <Button
              variant="outline"
              size="sm"
              onClick={() => loadSummary(true)}
              disabled={loading}
              className="h-7 text-xs flex items-center gap-1.5"
            >
              <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
              Regenerate
            </Button>
          </div>
        </div>

        {/* Content Body */}
        <div className="p-5 overflow-y-auto space-y-4 flex-1">
          {loading ? (
            <div className="py-12 flex flex-col items-center justify-center text-center space-y-3">
              <RefreshCw className="w-6 h-6 text-accent animate-spin" />
              <p className="text-xs text-secondary">
                Analyzing document chunks and extracting evidence-backed synthesis...
              </p>
            </div>
          ) : error ? (
            <div className="p-3.5 rounded bg-red-500/10 border border-red-500/20 text-xs text-red-600 dark:text-red-400">
              {error}
            </div>
          ) : summaryData ? (
            <>
              {/* Executive Summary */}
              <div className="space-y-2">
                <h4 className="text-xs font-semibold text-primary uppercase tracking-wider">
                  Summary Synthesis
                </h4>
                <div className="text-xs leading-relaxed text-secondary bg-panel/30 border border-border/60 rounded p-3.5 whitespace-pre-line">
                  {summaryData.summary}
                </div>
              </div>

              {/* Key Takeaways */}
              {summaryData.key_takeaways && summaryData.key_takeaways.length > 0 && (
                <div className="space-y-2">
                  <h4 className="text-xs font-semibold text-primary uppercase tracking-wider">
                    Core Findings & Takeaways
                  </h4>
                  <ul className="space-y-1.5">
                    {summaryData.key_takeaways.map((item, idx) => (
                      <li
                        key={idx}
                        className="text-xs text-secondary flex items-start gap-2 bg-panel/20 p-2 rounded border border-border/40"
                      >
                        <CheckCircle2 className="w-3.5 h-3.5 text-accent shrink-0 mt-0.5" />
                        <span>{item}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          ) : null}
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-border bg-panel/40 flex items-center justify-between">
          <Button
            variant="outline"
            size="sm"
            onClick={handleCopy}
            disabled={!summaryData || loading}
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
                Copy Summary
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

export default SummaryModal;
