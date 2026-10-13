import React, { useState, useRef, useEffect } from "react";
import {
  Send,
  Sparkles,
  MessageSquare,
  AlertCircle,
  Loader2,
  Menu,
  Network,
  Compass,
  AlertTriangle,
  CheckCircle2,
} from "lucide-react";
import EmptyState from "../common/EmptyState";
import MessageItem, { MessageProps, MessageCitation } from "./MessageItem";
import SourceInspectionModal from "./SourceInspectionModal";
import KnowledgeGraphModal from "./KnowledgeGraphModal";
import { Link } from "react-router-dom";
import { queryRAG } from "../../services/chatService";
import { researchService } from "../../services/researchService";
import { CitationItem } from "../../types/chat";

export interface ChatBoxProps {
  initialMessages?: MessageProps[];
  messages?: MessageProps[];
  conversationTitle?: string;
  conversationId?: string | null;
  onSendMessage?: (query: string, isDeepResearch?: boolean) => Promise<void>;
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

  // Deep research & Knowledge Graph state
  const [deepResearchMode, setDeepResearchMode] = useState(false);
  const [showKnowledgeGraph, setShowKnowledgeGraph] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const messages = externalMessages !== undefined ? externalMessages : internalMessages;
  const loading = externalLoading !== undefined ? externalLoading : internalLoading;
  const error = externalError !== undefined ? externalError : internalError;

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const query = inputValue.trim();
    if (!query || loading) return;

    if (onSendMessage) {
      setInputValue("");
      await onSendMessage(query, deepResearchMode);
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
      if (deepResearchMode) {
        // Deep Research execution
        const res = await researchService.executeDeepResearch({ topic: query });
        const assistantTimestamp = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

        const citations: MessageCitation[] = (res.sources || []).map((s, idx) => ({
          citationId: `cit_${idx}`,
          sourceName: s.filename,
          page: s.page_number,
          rawCitation: {
            citation_id: `cit_${idx}`,
            document_id: s.document_id,
            document_filename: s.filename,
            chunk_id: "",
            chunk_index: idx,
            page_number: s.page_number,
            similarity_score: 1.0,
            cosine_distance: 0.0,
            metadata: { snippet: s.excerpt },
          },
        }));

        let content = `### Deep Research Dossier: ${res.topic}\n\n`;
        if (res.subquestions && res.subquestions.length > 0) {
          content += `**Decomposed Inquiries:**\n${res.subquestions.map((q) => `- ${q}`).join("\n")}\n\n`;
        }
        if (res.has_conflicts) {
          content += `> **Caution:** Potential contradictory or conflicting evidence detected across source documents.\n\n`;
        }
        content += res.synthesis;

        const assistantMessage: MessageProps = {
          role: "assistant",
          content,
          citations,
          timestamp: assistantTimestamp,
        };

        setInternalMessages((prev) => [...prev, assistantMessage]);
      } else {
        // Standard RAG execution
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
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail;
      setInternalError(typeof detail === "string" ? detail : "Failed to synthesize answer.");
    } finally {
      setInternalLoading(false);
    }
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-surface">
      {/* Header Bar */}
      <div className="p-3.5 sm:p-4 border-b border-border flex items-center justify-between gap-3 bg-panel/30">
        <div className="flex items-center gap-2.5 min-w-0">
          {showSidebarToggle && (
            <button
              onClick={onToggleSidebar}
              className="md:hidden p-1.5 rounded text-secondary hover:text-primary hover:bg-panel transition-colors shrink-0 cursor-pointer"
              aria-label="Toggle conversation history"
            >
              <Menu className="w-4 h-4" />
            </button>
          )}

          <div className="min-w-0">
            <h2 className="text-xs sm:text-sm font-semibold text-primary truncate">
              {conversationTitle || "Ask Cogniva"}
            </h2>
            <p className="text-[10px] text-secondary">
              Grounded multimodal retrieval with verified citations
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={() => setShowKnowledgeGraph(true)}
            className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded text-xs font-medium border border-border bg-surface hover:bg-panel text-primary transition-colors cursor-pointer"
            title="Explore extracted entity relationships"
          >
            <Network className="w-3.5 h-3.5 text-accent" />
            <span className="hidden sm:inline">Knowledge Graph</span>
          </button>

          <span className="hidden sm:inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-medium bg-panel border border-border text-secondary">
            <span className="w-1.5 h-1.5 rounded-full bg-accent" />
            Grounded Model
          </span>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
        {messages.length === 0 ? (
          <EmptyState
            icon={<MessageSquare className="w-6 h-6" />}
            title="Enterprise Knowledge Intelligence"
            description="Ask questions about your uploaded PDFs, policies, and contracts. Cogniva returns deterministic answers grounded exclusively in verified sources."
            action={
              <div className="flex flex-wrap items-center justify-center gap-2 mt-2">
                <Link
                  to="/documents"
                  className="text-xs text-accent hover:underline font-medium"
                >
                  Manage documents →
                </Link>
              </div>
            }
          />
        ) : (
          <>
            {messages.map((msg, index) => (
              <MessageItem
                key={index}
                role={msg.role}
                content={msg.content}
                citations={msg.citations}
                timestamp={msg.timestamp}
                onInspectCitation={(citation) => setSelectedCitation(citation)}
              />
            ))}

            {/* Thinking / Retrieval state */}
            {loading && (
              <div className="flex items-start gap-3 mb-5">
                <div className="w-7 h-7 rounded-md bg-panel border border-border flex items-center justify-center shrink-0">
                  <Sparkles className="w-3.5 h-3.5 text-accent animate-pulse" />
                </div>
                <div className="p-3.5 rounded-xl border border-border bg-surface text-secondary text-xs flex items-center gap-2 shadow-2xs">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-accent" />
                  <span>
                    {deepResearchMode
                      ? "Executing multi-pass inquiry decomposition and evidence synthesis..."
                      : "Synthesizing grounded answer with source provenance..."}
                  </span>
                </div>
              </div>
            )}

            {/* Error banner */}
            {error && (
              <div className="p-3 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0" />
                <span className="flex-1">{error}</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </>
        )}
      </div>

      {/* Input Form Bar */}
      <div className="p-3 sm:p-4 border-t border-border bg-surface">
        {/* Research Mode Toggle Bar */}
        <div className="flex items-center justify-between mb-2 px-1 text-xs">
          <button
            type="button"
            onClick={() => setDeepResearchMode(!deepResearchMode)}
            className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[11px] font-medium transition-colors cursor-pointer border ${
              deepResearchMode
                ? "bg-accent/15 border-accent text-accent"
                : "bg-panel/60 border-border text-secondary hover:text-primary"
            }`}
          >
            <Compass className="w-3 h-3" />
            <span>Deep Research Mode</span>
            {deepResearchMode && <span className="text-[10px] uppercase font-bold">• Active</span>}
          </button>
          <span className="text-[10px] text-secondary">
            {deepResearchMode
              ? "Decomposes inquiries into subquestions & detects contradictions"
              : "Standard grounded semantic retrieval"}
          </span>
        </div>

        <form onSubmit={handleSubmit} className="relative flex items-center gap-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            disabled={loading}
            placeholder={
              deepResearchMode
                ? "Enter research inquiry (e.g. 'Investigate all regulatory non-compliance risks and remediation milestones')..."
                : "Ask a question about your knowledge repository (e.g. 'What are the termination clauses in the contract?')..."
            }
            className="flex-1 bg-panel/60 border border-border rounded-lg pl-3.5 pr-10 py-2.5 text-xs sm:text-sm text-primary placeholder:text-secondary/70 focus:outline-none focus:border-accent focus:ring-1 focus:ring-accent transition-colors disabled:opacity-50"
          />

          <button
            type="submit"
            disabled={!inputValue.trim() || loading}
            aria-label="Send query"
            className="px-3.5 py-2.5 rounded-lg bg-[#267653] dark:bg-[#42B883] hover:bg-[#1E5D42] dark:hover:bg-[#36996D] text-white dark:text-[#121614] transition-colors disabled:opacity-40 disabled:cursor-not-allowed shrink-0 cursor-pointer shadow-xs"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <Send className="w-4 h-4" />
            )}
          </button>
        </form>

        <p className="mt-2 text-[10px] text-secondary text-center">
          Answers are strictly synthesized from retrieved enterprise document chunks. Hallucinated sources are discarded.
        </p>
      </div>

      {/* Source Inspection Modal */}
      <SourceInspectionModal
        citation={selectedCitation}
        onClose={() => setSelectedCitation(null)}
      />

      {/* Knowledge Graph Modal */}
      {showKnowledgeGraph && (
        <KnowledgeGraphModal onClose={() => setShowKnowledgeGraph(false)} />
      )}
    </div>
  );
};

export default ChatBox;
