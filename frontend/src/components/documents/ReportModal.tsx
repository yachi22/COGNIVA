import React, { useState } from "react";
import { X, FileText, Download, RefreshCw, CheckCircle2, Copy, Check } from "lucide-react";
import Button from "../common/Button";
import { DocumentItem } from "../../types/document";
import { ReportGenerateResponse } from "../../types/intelligence";
import { intelligenceService } from "../../services/intelligenceService";

interface ReportModalProps {
  documents: DocumentItem[];
  selectedDocumentIds?: string[];
  onClose: () => void;
}

export const ReportModal: React.FC<ReportModalProps> = ({
  documents,
  selectedDocumentIds = [],
  onClose,
}) => {
  const [topic, setTopic] = useState("");
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [report, setReport] = useState<ReportGenerateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleGenerate = async () => {
    if (!topic.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await intelligenceService.generateReport({
        topic: topic.trim(),
        title: title.trim() || undefined,
        document_ids: selectedDocumentIds.length > 0 ? selectedDocumentIds : undefined,
      });
      setReport(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to generate report.");
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = () => {
    if (!report) return;
    const blob = new Blob([report.content_markdown], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${report.title.toLowerCase().replace(/[^a-z0-9]+/g, "_")}.md`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  const handleCopy = () => {
    if (!report) return;
    navigator.clipboard.writeText(report.content_markdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div className="bg-surface border border-border rounded-lg shadow-xl w-full max-w-3xl max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="p-4 border-b border-border flex items-center justify-between bg-panel/40">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded bg-accent/15 border border-accent/25 flex items-center justify-center text-accent">
              <FileText className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-primary">Evidence Research Report Generator</h3>
              <p className="text-xs text-secondary">
                Compile comprehensive, cited dossiers from your enterprise knowledge base
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

        {/* Inputs */}
        <div className="p-4 border-b border-border bg-panel/20 space-y-3">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
            <div>
              <label className="text-[11px] font-semibold text-secondary uppercase tracking-wider block mb-1">
                Report Title (Optional)
              </label>
              <input
                type="text"
                placeholder="e.g. Q3 Vendor Risk Assessment Dossier"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="w-full text-xs px-3 py-2 rounded bg-surface border border-border text-primary placeholder:text-secondary/60 focus:outline-none focus:ring-1 focus:ring-accent"
              />
            </div>
            <div>
              <label className="text-[11px] font-semibold text-secondary uppercase tracking-wider block mb-1">
                Research Scope
              </label>
              <div className="text-xs px-3 py-2 rounded bg-panel border border-border text-primary">
                {selectedDocumentIds.length > 0
                  ? `${selectedDocumentIds.length} Selected Documents`
                  : `Entire Library (${documents.length} Documents)`}
              </div>
            </div>
          </div>

          <div>
            <label className="text-[11px] font-semibold text-secondary uppercase tracking-wider block mb-1">
              Research Objective / Inquiry Topic *
            </label>
            <div className="flex gap-2">
              <input
                type="text"
                placeholder="e.g. Summarize compliance requirements, liability caps, and notice periods..."
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                className="flex-1 text-xs px-3 py-2 rounded bg-surface border border-border text-primary placeholder:text-secondary/60 focus:outline-none focus:ring-1 focus:ring-accent"
              />
              <Button
                variant="primary"
                size="sm"
                onClick={handleGenerate}
                disabled={loading || !topic.trim()}
                className="shrink-0 text-xs flex items-center gap-1.5"
              >
                {loading ? (
                  <>
                    <RefreshCw className="w-3 h-3 animate-spin" />
                    Synthesizing...
                  </>
                ) : (
                  <>Generate Report</>
                )}
              </Button>
            </div>
          </div>
        </div>

        {/* Body Preview */}
        <div className="p-5 overflow-y-auto space-y-4 flex-1">
          {loading ? (
            <div className="py-16 flex flex-col items-center justify-center text-center space-y-3">
              <RefreshCw className="w-7 h-7 text-accent animate-spin" />
              <p className="text-xs text-secondary max-w-sm">
                Assembling multi-section report with executive summary, detailed findings, and verified references...
              </p>
            </div>
          ) : error ? (
            <div className="p-3.5 rounded bg-red-500/10 border border-red-500/20 text-xs text-red-600 dark:text-red-400">
              {error}
            </div>
          ) : report ? (
            <div className="space-y-3">
              <div className="flex items-center justify-between text-xs pb-2 border-b border-border">
                <span className="font-semibold text-primary">{report.title}</span>
                <span className="text-secondary text-[11px]">
                  Generated: {new Date(report.generated_at).toLocaleString()}
                </span>
              </div>
              <div className="text-xs leading-relaxed text-secondary bg-panel/20 border border-border/70 rounded p-4 whitespace-pre-line font-mono">
                {report.content_markdown}
              </div>
            </div>
          ) : (
            <div className="py-12 text-center text-xs text-secondary">
              Enter a research objective above and click "Generate Report".
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-border bg-panel/40 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleCopy}
              disabled={!report || loading}
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
                  Copy Markdown
                </>
              )}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownload}
              disabled={!report || loading}
              className="text-xs flex items-center gap-1.5"
            >
              <Download className="w-3.5 h-3.5 text-accent" />
              Download (.md)
            </Button>
          </div>

          <Button variant="secondary" size="sm" onClick={onClose} className="text-xs">
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ReportModal;
