import React from "react";
import { FileText } from "lucide-react";

export interface CitationPillProps {
  citationId?: string;
  sourceName: string;
  page?: number | string | null;
  onClick?: () => void;
}

export const CitationPill: React.FC<CitationPillProps> = ({
  citationId,
  sourceName,
  page,
  onClick,
}) => {
  return (
    <button
      onClick={onClick}
      type="button"
      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded border border-border bg-panel hover:bg-panel/80 text-xs text-primary transition-colors cursor-pointer text-left font-medium select-none"
      title={citationId ? `Inspect source [${citationId}]: ${sourceName}` : `Inspect source: ${sourceName}`}
    >
      {citationId && (
        <span className="font-semibold text-accent font-mono text-[11px]">
          [{citationId}]
        </span>
      )}
      <FileText className="w-3 h-3 shrink-0 text-secondary" />
      <span className="truncate max-w-[180px]">{sourceName}</span>
      {page !== null && page !== undefined && (
        <span className="text-[10px] text-secondary font-mono">· p.{page}</span>
      )}
    </button>
  );
};

export default CitationPill;
