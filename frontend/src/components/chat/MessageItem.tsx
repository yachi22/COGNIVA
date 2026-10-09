import React from "react";
import { Sparkles, User as UserIcon } from "lucide-react";
import CitationPill from "./CitationPill";
import { CitationItem } from "../../types/chat";

export interface MessageCitation {
  citationId?: string;
  sourceName: string;
  page?: number | string | null;
  rawCitation?: CitationItem;
}

export interface MessageProps {
  role: "user" | "assistant" | "system";
  content: string;
  citations?: MessageCitation[];
  timestamp?: string;
  onInspectCitation?: (citation: CitationItem) => void;
}

export const MessageItem: React.FC<MessageProps> = ({
  role,
  content,
  citations = [],
  timestamp,
  onInspectCitation,
}) => {
  const isUser = role === "user";

  return (
    <div className={`flex gap-3.5 ${isUser ? "flex-row-reverse" : "flex-row"} mb-5`}>
      {/* Avatar */}
      <div
        className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
          isUser
            ? "bg-indigo-600 text-white shadow-xs"
            : "bg-gradient-to-tr from-purple-600 to-indigo-600 text-white shadow-xs"
        }`}
      >
        {isUser ? <UserIcon className="w-4 h-4" /> : <Sparkles className="w-4 h-4" />}
      </div>

      {/* Bubble container */}
      <div className={`max-w-[82%] sm:max-w-[75%] ${isUser ? "text-right" : "text-left"}`}>
        <div
          className={`inline-block p-4 rounded-2xl text-sm leading-relaxed shadow-xs text-left ${
            isUser
              ? "bg-indigo-600 text-white rounded-tr-xs"
              : "bg-white border border-slate-200 text-slate-800 rounded-tl-xs"
          }`}
        >
          <div className="whitespace-pre-wrap">{content}</div>

          {/* Sources / Citations section */}
          {!isUser && citations.length > 0 && (
            <div className="mt-3.5 pt-3 border-t border-slate-100">
              <p className="text-[11px] font-semibold tracking-wider text-slate-400 uppercase mb-2">
                Validated Citations & Sources
              </p>
              <div className="flex flex-wrap gap-1.5">
                {citations.map((c, i) => (
                  <CitationPill
                    key={i}
                    citationId={c.citationId}
                    sourceName={c.sourceName}
                    page={c.page}
                    onClick={() => {
                      if (c.rawCitation && onInspectCitation) {
                        onInspectCitation(c.rawCitation);
                      }
                    }}
                  />
                ))}
              </div>
            </div>
          )}
        </div>

        {timestamp && (
          <p className="text-[11px] text-slate-400 mt-1 px-1">{timestamp}</p>
        )}
      </div>
    </div>
  );
};

export default MessageItem;
