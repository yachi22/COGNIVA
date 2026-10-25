import React, { useState, useEffect } from "react";
import { X, Table, Download, RefreshCw, FileText, CheckCircle2, AlertTriangle, ShieldCheck } from "lucide-react";
import Button from "../common/Button";
import Badge from "../common/Badge";
import { DocumentItem } from "../../types/document";
import { StructuredExtractionResponse } from "../../types/intelligence";
import { intelligenceService } from "../../services/intelligenceService";

interface StructuredExtractModalProps {
  document: DocumentItem | null;
  onClose: () => void;
}

export const StructuredExtractModal: React.FC<StructuredExtractModalProps> = ({
  document,
  onClose,
}) => {
  const [loading, setLoading] = useState(false);
  const [data, setData] = useState<StructuredExtractionResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (document) {
      loadData();
    } else {
      setData(null);
      setError(null);
    }
  }, [document]);

  const loadData = async () => {
    if (!document) return;
    setLoading(true);
    setError(null);
    try {
      const res = await intelligenceService.extractStructured(document.id);
      setData(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to extract structured fields.");
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadCsv = () => {
    if (!document) return;
    const url = intelligenceService.getStructuredCsvExportUrl(document.id);
    window.open(url, "_blank");
  };

  if (!document) return null;

  const categories = data?.data || {};

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div className="bg-surface border border-border rounded-lg shadow-xl w-full max-w-3xl max-h-[85vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="p-4 border-b border-border flex items-center justify-between bg-panel/40">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded bg-accent/15 border border-accent/25 flex items-center justify-center text-accent">
              <Table className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-primary">Structured Information Extraction</h3>
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

        {/* Toolbar */}
        <div className="px-4 py-2.5 border-b border-border bg-canvas/40 flex items-center justify-between flex-wrap gap-2 text-xs">
          <span className="text-secondary">
            Extracted categories: Dates, Key Entities, Metrics, Obligations, Risks, Action Items
          </span>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownloadCsv}
              disabled={!data || loading}
              className="h-7 text-xs flex items-center gap-1.5"
            >
              <Download className="w-3 h-3 text-accent" />
              Download CSV
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={loadData}
              disabled={loading}
              className="h-7 text-xs flex items-center gap-1.5"
            >
              <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
              Re-extract
            </Button>
          </div>
        </div>

        {/* Body */}
        <div className="p-5 overflow-y-auto space-y-4 flex-1">
          {loading ? (
            <div className="py-12 flex flex-col items-center justify-center text-center space-y-3">
              <RefreshCw className="w-6 h-6 text-accent animate-spin" />
              <p className="text-xs text-secondary">
                Running bounded LLM schema extraction across document sections...
              </p>
            </div>
          ) : error ? (
            <div className="p-3.5 rounded bg-red-500/10 border border-red-500/20 text-xs text-red-600 dark:text-red-400">
              {error}
            </div>
          ) : data ? (
            <div className="space-y-4">
              {Object.entries(categories).map(([category, items]) => {
                const list = Array.isArray(items) ? items : [items];
                if (!list || list.length === 0) return null;

                return (
                  <div key={category} className="border border-border rounded-lg overflow-hidden">
                    <div className="px-3.5 py-2 bg-panel/60 border-b border-border flex items-center justify-between">
                      <span className="text-xs font-semibold text-primary capitalize">
                        {category.replace(/_/g, " ")}
                      </span>
                      <span className="text-[10px] text-secondary font-mono">
                        {list.length} {list.length === 1 ? "entry" : "entries"}
                      </span>
                    </div>

                    <div className="divide-y divide-border/60 bg-surface">
                      {list.map((item: any, idx: number) => {
                        const isObject = typeof item === "object" && item !== null;
                        const value = isObject
                          ? item.name || item.metric || item.risk || item.item || item.obligation || item.date || item.value || item.entity || item.description || JSON.stringify(item)
                          : String(item);
                        const context = isObject
                          ? item.type || item.unit || item.context || item.severity || item.event || item.provenance
                          : null;

                        return (
                          <div key={idx} className="p-3 text-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2 hover:bg-panel/20 transition-colors">
                            <span className="font-medium text-primary">
                              {value}
                            </span>
                            {context && (
                              <span className="text-[11px] text-secondary bg-panel px-2 py-0.5 rounded border border-border/50 shrink-0">
                                {context}
                              </span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : null}
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-border bg-panel/40 flex items-center justify-end">
          <Button variant="secondary" size="sm" onClick={onClose} className="text-xs">
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};

export default StructuredExtractModal;
