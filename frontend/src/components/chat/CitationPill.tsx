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
      className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-indigo-50/80 hover:bg-indigo-100/80 border border-indigo-200/80 text-xs font-medium text-indigo-700 transition-all cursor-pointer text-left shadow-2xs hover:shadow-xs"
      title={citationId ? `Inspect source [${citationId}]: ${sourceName}` : `Inspect source: ${sourceName}`}
    >
      {citationId && (
        <span className="font-semibold text-indigo-800 bg-indigo-100 px-1.5 py-0.5 rounded text-[10px]">
          [{citationId}]
        </span>
      )}
      <FileText className="w-3 h-3 shrink-0 text-indigo-500" />
      <span className="truncate max-w-[200px]">{sourceName}</span>
      {page !== null && page !== undefined && (
        <span className="text-[11px] text-indigo-500 font-normal">· p.{page}</span>
      )}
    </button>
  );
};

export default CitationPill;
