import React, { useState, useRef, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  Send,
  Sparkles,
  MessageSquare,
  AlertCircle,
  Loader2,
  Menu,
  Network,
  Compass,
  FileText,
  X,
  ChevronDown,
  Layers,
  HelpCircle,
  Shield,
} from "lucide-react";
import EmptyState from "../common/EmptyState";
import MessageItem, { MessageProps, MessageCitation } from "./MessageItem";
import SourceInspectionModal from "./SourceInspectionModal";
import KnowledgeGraphModal from "./KnowledgeGraphModal";
import DocumentViewerModal from "../documents/DocumentViewerModal";
import { queryRAG } from "../../services/chatService";
import { researchService } from "../../services/researchService";
import { useDocuments } from "../../hooks/useDocuments";
import { CitationItem } from "../../types/chat";
import { DocumentItem } from "../../types/document";

export interface ChatBoxProps {
  initialMessages?: MessageProps[];
  messages?: MessageProps[];
  conversationTitle?: string;
  conversationId?: string | null;
  onSendMessage?: (query: string, isDeepResearch?: boolean, documentId?: string | null) => Promise<void>;
  loading?: boolean;
  error?: string | null;
  onToggleSidebar?: () => void;
  showSidebarToggle?: boolean;
  initialDocumentId?: string | null;
  initialQuery?: string | null;
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
  initialDocumentId,
  initialQuery,
}) => {
  const { documents } = useDocuments();

  const [internalMessages, setInternalMessages] = useState<MessageProps[]>(initialMessages || []);
  const [inputValue, setInputValue] = useState(initialQuery || "");
  const [internalLoading, setInternalLoading] = useState(false);
  const [internalError, setInternalError] = useState<string | null>(null);
  const [selectedCitation, setSelectedCitation] = useState<CitationItem | null>(null);

  // Document references & scoping
  const [selectedDocId, setSelectedDocId] = useState<string | null>(initialDocumentId || null);
  const [docDropdownOpen, setDocDropdownOpen] = useState(false);
  const [viewerDoc, setViewerDoc] = useState<DocumentItem | null>(null);

  // Deep research & Knowledge Graph state
  const [deepResearchMode, setDeepResearchMode] = useState(false);
  const [showKnowledgeGraph, setShowKnowledgeGraph] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const messages = externalMessages !== undefined ? externalMessages : internalMessages;
  const loading = externalLoading !== undefined ? externalLoading : internalLoading;
  const error = externalError !== undefined ? externalError : internalError;

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, loading]);

  useEffect(() => {
    if (initialDocumentId) {
      setSelectedDocId(initialDocumentId);
    }
  }, [initialDocumentId]);

  useEffect(() => {
    if (initialQuery) {
      setInputValue(initialQuery);
    }
  }, [initialQuery]);

  // Close dropdown on outside click
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDocDropdownOpen(false);
      }
    };
    document.addEventListener("mousedown", handleOutsideClick);
    return () => document.removeEventListener("mousedown", handleOutsideClick);
  }, []);

  const selectedDocument = documents.find((d) => d.id === selectedDocId);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const query = inputValue.trim();
    if (!query || loading) return;

    if (onSendMessage) {
      setInputValue("");
      await onSendMessage(query, deepResearchMode, selectedDocId);
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
        const res = await researchService.executeDeepResearch({
          topic: query,
          document_id: selectedDocId || undefined,
        });
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
        const response = await queryRAG({
          query,
          document_id: selectedDocId || null,
          conversation_id: conversationId,
        });
        const assistantTimestamp = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

        const citations: MessageCitation[] = (response.citations && response.citations.length > 0 && !response.insufficient_evidence)
          ? response.citations.map((c) => ({
              citationId: c.citation_id,
              sourceName: c.document_filename,
              page: c.page_number,
              rawCitation: c,
            }))
          : [];

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

  const samplePrompts = [
    "What are the primary operational obligations, deadlines, and milestones?",
    "Summarize all key financial metrics, pricing, and fee structures.",
    "What governing law, liability caps, and termination clauses apply?",
    "Detect any potential contradictions or compliance exceptions.",
  ];

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

      {/* Document Reference Filter Strip */}
      <div className="px-4 py-2 border-b border-border bg-panel/20 flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-2 min-w-0" ref={dropdownRef}>
          <span className="text-[11px] font-medium text-secondary shrink-0">
            Reference Scope:
          </span>

          <div className="relative">
            <button
              type="button"
              onClick={() => setDocDropdownOpen(!docDropdownOpen)}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-medium border border-border bg-surface hover:bg-panel text-primary transition-colors cursor-pointer truncate max-w-[220px] sm:max-w-xs"
            >
              <FileText className="w-3 h-3 text-accent shrink-0" />
              <span className="truncate">
                {selectedDocument
                  ? selectedDocument.original_filename || selectedDocument.filename
                  : "All Knowledge Bases (Global)"}
              </span>
              <ChevronDown className="w-3 h-3 text-secondary shrink-0 ml-0.5" />
            </button>

            {docDropdownOpen && (
              <div className="absolute left-0 mt-1 w-72 bg-surface border border-border rounded-lg shadow-xl z-40 py-1 max-h-60 overflow-y-auto">
                <button
                  type="button"
                  onClick={() => {
                    setSelectedDocId(null);
                    setDocDropdownOpen(false);
                  }}
                  className={`w-full px-3 py-1.5 text-left text-xs flex items-center justify-between hover:bg-panel cursor-pointer ${
                    selectedDocId === null ? "text-accent font-semibold bg-panel/50" : "text-primary"
                  }`}
                >
                  <span>All Knowledge Bases (Global)</span>
                  <span className="text-[10px] text-secondary font-mono">{documents.length} docs</span>
                </button>

                <div className="border-t border-border my-1" />

                {documents.length === 0 ? (
                  <p className="px-3 py-2 text-xs text-secondary italic">No documents indexed</p>
                ) : (
                  documents.map((doc) => (
                    <button
                      key={doc.id}
                      type="button"
                      onClick={() => {
                        setSelectedDocId(doc.id);
                        setDocDropdownOpen(false);
                      }}
                      className={`w-full px-3 py-1.5 text-left text-xs flex items-center justify-between hover:bg-panel cursor-pointer ${
                        selectedDocId === doc.id ? "text-accent font-semibold bg-panel/50" : "text-primary"
                      }`}
                    >
                      <span className="truncate pr-2">{doc.original_filename || doc.filename}</span>
                      <span className="text-[10px] font-mono text-secondary shrink-0">
                        {doc.file_type.toUpperCase()}
                      </span>
                    </button>
                  ))
                )}
              </div>
            )}
          </div>

          {selectedDocument && (
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => setViewerDoc(selectedDocument)}
                className="text-[11px] text-accent hover:underline font-medium cursor-pointer"
              >
                View Insights
              </button>
              <button
                type="button"
                onClick={() => setSelectedDocId(null)}
                className="p-1 rounded text-secondary hover:text-primary hover:bg-panel cursor-pointer"
                title="Clear document filter"
              >
                <X className="w-3 h-3" />
              </button>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2 shrink-0 text-[10px] text-secondary">
          <span className="flex items-center gap-1 font-mono">
            <Shield className="w-3 h-3 text-accent" /> Tenant Isolated
          </span>
        </div>
      </div>

      {/* Messages Scroll Area */}
      <div className="flex-1 overflow-y-auto p-4 sm:p-6 space-y-4">
        {messages.length === 0 ? (
          <div className="space-y-6 max-w-xl mx-auto py-6">
            <EmptyState
              icon={<MessageSquare className="w-6 h-6" />}
              title="Enterprise Multimodal Knowledge Agent"
              description="Ask questions about your uploaded documents, policies, and contracts. Cogniva returns deterministic answers grounded exclusively in verified sources."
            />

            {/* Quick Starter Prompts */}
            <div className="space-y-2">
              <span className="text-[11px] font-semibold text-secondary uppercase tracking-wider block text-center">
                Suggested Strategic Inquiries
              </span>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {samplePrompts.map((prompt, i) => (
                  <button
                    key={i}
                    type="button"
                    onClick={() => setInputValue(prompt)}
                    className="p-2.5 rounded-lg border border-border bg-panel/30 hover:bg-panel/70 text-left text-xs text-primary transition-colors cursor-pointer group flex items-start gap-2"
                  >
                    <HelpCircle className="w-3.5 h-3.5 text-accent shrink-0 mt-0.5 group-hover:scale-110 transition-transform" />
                    <span className="leading-relaxed">{prompt}</span>
                  </button>
                ))}
              </div>
            </div>
          </div>
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
        {/* Deep Research Control & Mode Selector */}
        <div className="flex items-center justify-between mb-2 px-1 text-xs">
          <div className="flex items-center gap-1.5 bg-panel p-0.5 rounded-lg border border-border">
            <button
              type="button"
              onClick={() => setDeepResearchMode(false)}
              className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors cursor-pointer flex items-center gap-1.5 ${
                !deepResearchMode
                  ? "bg-surface text-primary font-semibold shadow-2xs"
                  : "text-secondary hover:text-primary"
              }`}
            >
              <FileText className="w-3 h-3" />
              <span>Standard RAG</span>
            </button>
            <button
              type="button"
              onClick={() => setDeepResearchMode(true)}
              className={`px-2.5 py-1 rounded-md text-[11px] font-medium transition-colors cursor-pointer flex items-center gap-1.5 ${
                deepResearchMode
                  ? "bg-accent/15 text-accent border border-accent/30 font-semibold shadow-2xs"
                  : "text-secondary hover:text-primary"
              }`}
            >
              <Compass className="w-3 h-3" />
              <span>Deep Research</span>
              {deepResearchMode && <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />}
            </button>
          </div>

          <span className="text-[10px] text-secondary hidden sm:inline">
            {deepResearchMode
              ? "Multi-step inquiry decomposition & cross-source conflict detection"
              : "Direct semantic retrieval with verified citation chunks"}
          </span>
        </div>

        <form onSubmit={handleSubmit} className="relative flex items-center gap-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            disabled={loading}
            placeholder={
              selectedDocument
                ? `Ask question scoped to ${selectedDocument.original_filename || selectedDocument.filename}...`
                : deepResearchMode
                ? "Enter research topic for comprehensive multi-turn synthesis..."
                : "Ask a grounded question across your knowledge repository..."
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
          Answers are synthesized strictly from retrieved enterprise document chunks. Hallucinated sources are discarded.
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

      {/* Document Viewer Modal */}
      {viewerDoc && (
        <DocumentViewerModal
          document={viewerDoc}
          onClose={() => setViewerDoc(null)}
        />
      )}
    </div>
  );
};

export default ChatBox;
