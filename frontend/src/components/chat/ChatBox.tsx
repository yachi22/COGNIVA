import React, { useState } from "react";
import { Send, Sparkles, MessageSquare, Info, AlertCircle, Loader2, Menu } from "lucide-react";
import EmptyState from "../common/EmptyState";
import MessageItem, { MessageProps } from "./MessageItem";
import SourceInspectionModal from "./SourceInspectionModal";
import { Link } from "react-router-dom";
import { queryRAG } from "../../services/chatService";
import { CitationItem } from "../../types/chat";

export interface ChatBoxProps {
  initialMessages?: MessageProps[];
  messages?: MessageProps[];
  conversationTitle?: string;
  conversationId?: string | null;
  onSendMessage?: (query: string) => Promise<void>;
  loading?: boolean;
  error?: string | null;
  onToggleSidebar?: () => void;
  showSidebarToggle?: boolean;
}

export const ChatBox: React.FC<ChatBoxProps> = ({
  initialMessages,
  messages: externalMessages,
  conversationTitle,
  conversationId,
  onSendMessage,
  loading: externalLoading,
  error: externalError,
  onToggleSidebar,
  showSidebarToggle,
}) => {
  const [internalMessages, setInternalMessages] = useState<MessageProps[]>(initialMessages || []);
  const [inputValue, setInputValue] = useState("");
  const [internalLoading, setInternalLoading] = useState(false);
  const [internalError, setInternalError] = useState<string | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<CitationItem | null>(null);

  // Controlled vs Uncontrolled
  const messages = externalMessages !== undefined ? externalMessages : internalMessages;
  const loading = externalLoading !== undefined ? externalLoading : internalLoading;
  const error = externalError !== undefined ? externalError : internalError;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const query = inputValue.trim();
    if (!query || loading) return;

    if (onSendMessage) {
      setInputValue("");
      await onSendMessage(query);
      return;
    }

    // Standalone fallback handling
    setInternalError(null);
    const userTimestamp = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    const userMessage: MessageProps = {
      role: "user",
      content: query,
      timestamp: userTimestamp,
    };

    setInternalMessages((prev) => [...prev, userMessage]);
    setInputValue("");
    setInternalLoading(true);

    try {
      const response = await queryRAG({ query, conversation_id: conversationId });
      const assistantTimestamp = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

      const citations = (response.citations && response.citations.length > 0)
        ? response.citations.map((c) => ({
            citationId: c.citation_id,
            sourceName: c.document_filename,
            page: c.page_number,
            rawCitation: c,
          }))
        : (response.sources || []).map((s) => ({
            citationId: s.citation_id,
            sourceName: s.document_filename,
            page: s.page_number,
            rawCitation: {
              citation_id: s.citation_id,
              document_id: s.document_id,
              document_filename: s.document_filename,
              chunk_id: s.chunk_id,
              chunk_index: s.chunk_index,
              page_number: s.page_number,
              similarity_score: s.similarity_score,
              cosine_distance: s.cosine_distance,
              metadata: s.metadata,
            },
          }));

      const assistantMessage: MessageProps = {
        role: "assistant",
        content: response.answer,
        citations,
        timestamp: assistantTimestamp,
      };
      setInternalMessages((prev) => [...prev, assistantMessage]);
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      const errorMsg = typeof detail === "string" ? detail : "Failed to generate answer. Please check LLM provider configuration or try again.";
      setInternalError(errorMsg);
    } finally {
      setInternalLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full bg-white overflow-hidden">
      {/* Chat Header */}
      <div className="p-4 sm:px-6 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
        <div className="flex items-center gap-3 min-w-0">
          {showSidebarToggle && (
            <button
              onClick={onToggleSidebar}
              className="md:hidden p-1.5 rounded-lg text-slate-500 hover:text-slate-700 hover:bg-slate-200/60 transition-colors shrink-0"
              title="Open conversation history"
            >
              <Menu className="w-4 h-4" />
            </button>
          )}

          <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600 shrink-0">
            <Sparkles className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-slate-900 truncate">
              {conversationTitle || "Ask Cogniva"}
            </h2>
            <p className="text-xs text-slate-500 truncate">
              {conversationTitle ? "Enterprise grounded knowledge agent" : "Ask questions about your organization's knowledge"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-emerald-50 text-emerald-700 border border-emerald-200/60">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            Citations & RAG: Active
          </span>
        </div>
      </div>

      {/* Message Stream or Polished Empty State */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <EmptyState
              icon={<MessageSquare className="w-6 h-6 text-indigo-600" />}
              title="Upload documents and start asking questions."
              description="Cogniva indexes your documents and retrieves grounded evidence to synthesize precise answers with provenance."
              action={
                <Link
                  to="/documents"
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-xs transition-colors"
                >
                  Go to Documents
                </Link>
              }
            />
          </div>
        ) : (
          <div>
            {messages.map((msg, idx) => (
              <MessageItem
                key={idx}
                {...msg}
                onInspectCitation={(c) => setSelectedCitation(c)}
              />
            ))}

            {loading && (
              <div className="flex gap-3.5 flex-row mb-5 items-center">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-purple-600 to-indigo-600 text-white flex items-center justify-center shadow-xs">
                  <Sparkles className="w-4 h-4 animate-spin" />
                </div>
                <div className="inline-flex items-center gap-2 px-4 py-3 rounded-2xl bg-slate-50 border border-slate-200 text-slate-600 text-xs">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-indigo-600" />
                  <span>Searching documents and generating grounded answer...</span>
                </div>
              </div>
            )}
          </div>
        )}

        {error && (
          <div className="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 text-xs flex items-center gap-2">
            <AlertCircle className="w-4 h-4 text-amber-600 shrink-0" />
            <span>{error}</span>
          </div>
        )}
      </div>

      {/* Input Composer Area */}
      <div className="p-4 border-t border-slate-100 bg-slate-50/50">
        <div className="mb-2 flex items-center gap-1.5 text-[11px] text-slate-500">
          <Info className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
          <span>
            Answers are strictly grounded in retrieved evidence with verified backend citations.
          </span>
        </div>

        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            disabled={loading}
            placeholder="Ask a question about your documents... (e.g., 'What is the leave policy?')"
            className="flex-1 px-4 py-2.5 text-sm bg-white border border-slate-200 rounded-xl placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-100 focus:border-indigo-500 disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={!inputValue.trim() || loading}
            className="px-4 py-2.5 bg-indigo-600 text-white rounded-xl text-sm font-medium hover:bg-indigo-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors flex items-center gap-1.5 shrink-0"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            <span className="hidden sm:inline">Ask</span>
          </button>
        </form>
      </div>

      {/* Source Inspection Modal */}
      <SourceInspectionModal
        citation={selectedCitation}
        onClose={() => setSelectedCitation(null)}
      />
    </div>
  );
};

export default ChatBox;
