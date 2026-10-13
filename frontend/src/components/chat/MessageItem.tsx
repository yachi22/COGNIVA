import React, { useState } from "react";
import { Sparkles, User as UserIcon, Copy, Check } from "lucide-react";
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
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    navigator.clipboard.writeText(content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"} mb-5 group`}>
      {/* Avatar */}
      <div
        className={`w-7 h-7 rounded-md flex items-center justify-center shrink-0 text-xs font-semibold ${
          isUser
            ? "bg-[#267653] dark:bg-[#42B883] text-white dark:text-[#121614]"
            : "bg-panel border border-border text-primary"
        }`}
      >
        {isUser ? <UserIcon className="w-3.5 h-3.5" /> : <Sparkles className="w-3.5 h-3.5 text-accent" />}
      </div>

      {/* Bubble container */}
      <div className={`max-w-[85%] sm:max-w-[80%] ${isUser ? "text-right" : "text-left"}`}>
        <div
          className={`relative inline-block p-4 rounded-xl text-xs sm:text-sm leading-relaxed text-left border ${
            isUser
              ? "bg-panel border-border text-primary rounded-tr-xs"
              : "bg-surface border-border text-primary rounded-tl-xs shadow-2xs"
          }`}
        >
          {/* Answer text */}
          <div className="whitespace-pre-wrap leading-relaxed select-text">{content}</div>

          {/* Copy button for assistant answers */}
          {!isUser && (
            <button
              onClick={handleCopy}
              className="absolute top-2.5 right-2.5 p-1 rounded text-secondary hover:text-primary hover:bg-panel transition-colors opacity-0 group-hover:opacity-100 cursor-pointer"
              title="Copy message"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-accent" /> : <Copy className="w-3.5 h-3.5" />}
            </button>
          )}

          {/* Validated Citations section */}
          {!isUser && citations.length > 0 && (
            <div className="mt-3.5 pt-3 border-t border-border">
              <p className="text-[10px] font-semibold tracking-wider text-secondary uppercase mb-2">
                Validated Evidence & Citations
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
          <p className="text-[10px] text-secondary mt-1 px-1">{timestamp}</p>
        )}
      </div>
    </div>
  );
};

export default MessageItem;
