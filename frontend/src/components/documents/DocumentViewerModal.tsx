import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import {
  X,
  FileText,
  Sparkles,
  CheckCircle2,
  RefreshCw,
  Copy,
  Check,
  Search,
  BookOpen,
  Hash,
  Layers,
  ArrowRight,
  HelpCircle,
  AlertCircle,
  Cpu,
  Shield,
  Clock,
  ExternalLink,
} from "lucide-react";
import Button from "../common/Button";
import Badge from "../common/Badge";
import EmptyState from "../common/EmptyState";
import {
  DocumentItem,
  DocumentChunkItem,
  ExtractedDocument,
} from "../../types/document";
import { DocumentSummaryResponse } from "../../types/intelligence";
import { intelligenceService } from "../../services/intelligenceService";
import { documentService } from "../../services/documentService";

interface DocumentViewerModalProps {
  document: DocumentItem | null;
  onClose: () => void;
  onProcess?: (id: string) => Promise<unknown>;
}

export const DocumentViewerModal: React.FC<DocumentViewerModalProps> = ({
  document,
  onClose,
  onProcess,
}) => {
  const navigate = useNavigate();

  const [activeTab, setActiveTab] = useState<"takeaways" | "citations" | "questions" | "raw">("takeaways");
  const [summaryMode, setSummaryMode] = useState<"concise" | "detailed">("concise");

  // Summary State
  const [summaryData, setSummaryData] = useState<DocumentSummaryResponse | null>(null);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [summaryError, setSummaryError] = useState<string | null>(null);

  // Chunks State
  const [chunks, setChunks] = useState<DocumentChunkItem[]>([]);
  const [loadingChunks, setLoadingChunks] = useState(false);
  const [chunksError, setChunksError] = useState<string | null>(null);
  const [chunkFilter, setChunkFilter] = useState("");

  // Extracted Units State
  const [extracted, setExtracted] = useState<ExtractedDocument | null>(null);
  const [loadingExtracted, setLoadingExtracted] = useState(false);

  // UI helpers
  const [copiedSummary, setCopiedSummary] = useState(false);
  const [copiedChunkId, setCopiedChunkId] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);

  useEffect(() => {
    if (!document) {
      setSummaryData(null);
      setChunks([]);
      setExtracted(null);
      return;
    }

    if (document.status === "processed") {
      loadSummary(false);
      loadChunks();
    }
  }, [document, summaryMode]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const loadSummary = async (forceRefresh: boolean = false) => {
    if (!document) return;
    setLoadingSummary(true);
    setSummaryError(null);
    try {
      const res = await intelligenceService.summarizeDocument(document.id, summaryMode, forceRefresh);
      setSummaryData(res);
    } catch (err: any) {
      setSummaryError(err?.response?.data?.detail || "Failed to generate document summary.");
    } finally {
      setLoadingSummary(false);
    }
  };

  const loadChunks = async () => {
    if (!document) return;
    setLoadingChunks(true);
    setChunksError(null);
    try {
      const res = await documentService.getDocumentChunks(document.id);
      setChunks(res.chunks || []);
    } catch (err: any) {
      setChunksError(err?.response?.data?.detail || "Failed to load document chunks.");
    } finally {
      setLoadingChunks(false);
    }
  };

  const loadExtracted = async () => {
    if (!document || extracted) return;
    setLoadingExtracted(true);
    try {
      const res = await documentService.getExtractedContent(document.id);
      setExtracted(res);
    } catch {
      // Ignored
    } finally {
      setLoadingExtracted(false);
    }
  };

  const handleTabChange = (tab: "takeaways" | "citations" | "questions" | "raw") => {
    setActiveTab(tab);
    if (tab === "raw" && !extracted) {
      loadExtracted();
    }
  };

  const handleCopySummary = () => {
    if (!summaryData) return;
    const text = `# Executive Summary: ${summaryData.document_filename}\n\n${summaryData.summary}\n\n## Key Takeaways:\n${summaryData.key_takeaways.map((t) => `- ${t}`).join("\n")}`;
    navigator.clipboard.writeText(text);
    setCopiedSummary(true);
    setTimeout(() => setCopiedSummary(false), 2000);
  };

  const handleCopyChunk = (chunkId: string, content: string) => {
    navigator.clipboard.writeText(content);
    setCopiedChunkId(chunkId);
    setTimeout(() => setCopiedChunkId(null), 2000);
  };

  const handleAskQuestion = (question: string) => {
    if (!document) return;
    onClose();
    navigate(`/chat?query=${encodeURIComponent(question)}&docId=${document.id}`);
  };

  const handleTriggerProcess = async () => {
    if (!document || !onProcess) return;
    setIsProcessing(true);
    try {
      await onProcess(document.id);
      loadSummary(false);
      loadChunks();
    } catch {
      // handled in parent
    } finally {
      setIsProcessing(false);
    }
  };

  if (!document) return null;

  const formatFileSize = (bytes?: number): string => {
    if (!bytes || bytes === 0) return "--";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const filteredChunks = chunks.filter((c) =>
    c.content.toLowerCase().includes(chunkFilter.toLowerCase())
  );

  // Suggested enterprise inquiry prompts based on the document
  const relatedQuestions = [
    {
      title: "Core Obligations & Milestones",
      prompt: `What are the primary operational obligations, deadlines, and milestones specified in ${document.original_filename || document.filename}?`,
      description: "Extracts all mandatory commitments, scheduled deliverables, and compliance target dates.",
    },
    {
      title: "Financial Terms & Fee Structure",
      prompt: `Summarize all financial terms, payment conditions, rates, or fiscal allocations defined in ${document.original_filename || document.filename}.`,
      description: "Identifies quantitative pricing matrices, expense schedules, and billing cycles.",
    },
    {
      title: "Governance & Termination Rights",
      prompt: `What are the governing conditions, breach triggers, and termination procedures outlined in ${document.original_filename || document.filename}?`,
      description: "Maps contractual governance rules, dispute escalation paths, and exit mechanisms.",
    },
    {
      title: "Liabilities, Warranties & Indemnification",
      prompt: `What liability limitations, warranties, risk disclosures, or indemnification provisions apply in ${document.original_filename || document.filename}?`,
      description: "Highlights legal protections, liability caps, and designated responsibility domains.",
    },
    {
      title: "Exceptions & Non-Compliance Penalties",
      prompt: `Identify any contractual exceptions, penalties, service credits, or risk factors detailed in ${document.original_filename || document.filename}.`,
      description: "Pins down potential breach penalties, remedies, and risk contingencies.",
    },
  ];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-4 bg-black/60 backdrop-blur-xs">
      <div
        className="bg-surface border border-border rounded-xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden text-primary transition-colors"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header Bar */}
        <div className="px-5 py-3.5 border-b border-border flex items-center justify-between bg-panel/40">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-9 h-9 rounded-lg bg-panel border border-border flex items-center justify-center text-accent shrink-0 shadow-2xs">
              <FileText className="w-5 h-5" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h2 className="text-sm sm:text-base font-semibold text-primary truncate">
                  {document.original_filename || document.filename}
                </h2>
                <Badge
                  variant={
                    document.status === "processed"
                      ? "success"
                      : document.status === "failed"
                      ? "danger"
                      : "warning"
                  }
                  size="xs"
                >
                  {document.status}
                </Badge>
                <Badge variant="neutral" size="xs">
                  {document.file_type.toUpperCase()}
                </Badge>
              </div>
              <p className="text-[11px] text-secondary mt-0.5 flex items-center gap-2">
                <span>Ingested {new Date(document.created_at).toLocaleDateString()}</span>
                <span>•</span>
                <span className="flex items-center gap-1 font-mono text-[10px]">
                  <Shield className="w-3 h-3 text-accent" /> Tenant Protected
                </span>
              </p>
            </div>
          </div>

          <div className="flex items-center gap-2 shrink-0">
            <Button
              variant="outline"
              size="xs"
              onClick={() => handleAskQuestion(`Summarize the key information in ${document.original_filename || document.filename}`)}
              icon={<ArrowRight className="w-3.5 h-3.5" />}
              className="hidden sm:inline-flex"
            >
              Ask in Chat
            </Button>
            <button
              onClick={onClose}
              className="p-1.5 rounded-md text-secondary hover:text-primary hover:bg-panel transition-colors cursor-pointer"
              title="Close viewer"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* 4-Metric Document Insights Strip */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 px-5 py-3 bg-panel/20 border-b border-border">
          <div className="p-2.5 rounded-lg bg-surface border border-border">
            <span className="text-[10px] font-medium text-secondary uppercase tracking-wider block">
              Document Scope
            </span>
            <div className="flex items-baseline gap-1.5 mt-1">
              <span className="text-sm sm:text-base font-bold text-primary">
                {document.metadata?.total_pages ? `${document.metadata.total_pages} Pages` : "1 File"}
              </span>
            </div>
          </div>

          <div className="p-2.5 rounded-lg bg-surface border border-border">
            <span className="text-[10px] font-medium text-secondary uppercase tracking-wider block">
              Lexical Volume
            </span>
            <div className="flex items-baseline gap-1.5 mt-1">
              <span className="text-sm sm:text-base font-bold text-primary">
                {document.metadata?.total_words
                  ? `${document.metadata.total_words.toLocaleString()} Words`
                  : "--"}
              </span>
            </div>
          </div>

          <div className="p-2.5 rounded-lg bg-surface border border-border">
            <span className="text-[10px] font-medium text-secondary uppercase tracking-wider block">
              Indexed Chunks
            </span>
            <div className="flex items-baseline gap-1.5 mt-1">
              <span className="text-sm sm:text-base font-bold text-accent">
                {chunks.length > 0 ? `${chunks.length} Chunks` : document.metadata?.total_units || "--"}
              </span>
            </div>
          </div>

          <div className="p-2.5 rounded-lg bg-surface border border-border">
            <span className="text-[10px] font-medium text-secondary uppercase tracking-wider block">
              Storage Footprint
            </span>
            <div className="flex items-baseline gap-1.5 mt-1">
              <span className="text-sm sm:text-base font-bold text-primary">
                {formatFileSize(document.metadata?.size_bytes)}
              </span>
            </div>
          </div>
        </div>

        {/* Tabs Bar */}
        <div className="px-5 border-b border-border flex items-center justify-between gap-4 bg-panel/30">
          <div className="flex items-center gap-1 sm:gap-2">
            <button
              onClick={() => handleTabChange("takeaways")}
              className={`px-3 py-2.5 text-xs font-semibold border-b-2 transition-colors cursor-pointer flex items-center gap-1.5 ${
                activeTab === "takeaways"
                  ? "border-accent text-accent"
                  : "border-transparent text-secondary hover:text-primary"
              }`}
            >
              <Sparkles className="w-3.5 h-3.5" />
              <span>Key Takeaways & Synthesis</span>
            </button>

            <button
              onClick={() => handleTabChange("citations")}
              className={`px-3 py-2.5 text-xs font-semibold border-b-2 transition-colors cursor-pointer flex items-center gap-1.5 ${
                activeTab === "citations"
                  ? "border-accent text-accent"
                  : "border-transparent text-secondary hover:text-primary"
              }`}
            >
              <Layers className="w-3.5 h-3.5" />
              <span>Provenance Chunks ({chunks.length})</span>
            </button>

            <button
              onClick={() => handleTabChange("questions")}
              className={`px-3 py-2.5 text-xs font-semibold border-b-2 transition-colors cursor-pointer flex items-center gap-1.5 ${
                activeTab === "questions"
                  ? "border-accent text-accent"
                  : "border-transparent text-secondary hover:text-primary"
              }`}
            >
              <HelpCircle className="w-3.5 h-3.5" />
              <span>Related Inquiries</span>
            </button>

            <button
              onClick={() => handleTabChange("raw")}
              className={`px-3 py-2.5 text-xs font-semibold border-b-2 transition-colors cursor-pointer flex items-center gap-1.5 ${
                activeTab === "raw"
                  ? "border-accent text-accent"
                  : "border-transparent text-secondary hover:text-primary"
              }`}
            >
              <BookOpen className="w-3.5 h-3.5" />
              <span className="hidden sm:inline">Extracted Units</span>
            </button>
          </div>

          {activeTab === "takeaways" && (
            <div className="flex items-center gap-2 py-1.5">
              <div className="flex items-center bg-panel p-0.5 rounded border border-border text-xs">
                <button
                  onClick={() => setSummaryMode("concise")}
                  className={`px-2 py-0.5 rounded font-medium transition-colors text-[11px] ${
                    summaryMode === "concise"
                      ? "bg-surface text-primary font-semibold shadow-2xs"
                      : "text-secondary hover:text-primary"
                  }`}
                >
                  Concise
                </button>
                <button
                  onClick={() => setSummaryMode("detailed")}
                  className={`px-2 py-0.5 rounded font-medium transition-colors text-[11px] ${
                    summaryMode === "detailed"
                      ? "bg-surface text-primary font-semibold shadow-2xs"
                      : "text-secondary hover:text-primary"
                  }`}
                >
                  Detailed
                </button>
              </div>

              <Button
                variant="outline"
                size="xs"
                onClick={() => loadSummary(true)}
                disabled={loadingSummary || document.status !== "processed"}
                icon={<RefreshCw className={`w-3 h-3 ${loadingSummary ? "animate-spin" : ""}`} />}
                className="text-[11px] h-6 px-2"
              >
                Regenerate
              </Button>
            </div>
          )}
        </div>

        {/* Tab Content Body */}
        <div className="flex-1 overflow-y-auto p-5 space-y-4">
          {/* TAB 1: Key Takeaways & Synthesis */}
          {activeTab === "takeaways" && (
            <>
              {document.status !== "processed" ? (
                <div className="p-8 text-center bg-panel/30 border border-border rounded-xl space-y-3">
                  <AlertCircle className="w-8 h-8 text-secondary mx-auto" />
                  <h3 className="text-sm font-semibold text-primary">
                    Document Extraction Incomplete
                  </h3>
                  <p className="text-xs text-secondary max-w-md mx-auto">
                    This document currently has status &quot;{document.status}&quot;. Executive summaries and key takeaways are computed once chunks are indexed in the vector repository.
                  </p>
                  {onProcess && document.status !== "processing" && (
                    <Button
                      variant="primary"
                      size="sm"
                      onClick={handleTriggerProcess}
                      disabled={isProcessing}
                      icon={<Cpu className="w-4 h-4" />}
                    >
                      {isProcessing ? "Processing Document..." : "Trigger Text Extraction Pipeline"}
                    </Button>
                  )}
                </div>
              ) : loadingSummary ? (
                <div className="py-16 text-center space-y-3">
                  <RefreshCw className="w-6 h-6 text-accent animate-spin mx-auto" />
                  <p className="text-xs text-secondary font-medium">
                    Synthesizing grounded takeaways and executive overview from authentic document chunks...
                  </p>
                </div>
              ) : summaryError ? (
                <div className="p-4 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-xs flex items-center justify-between">
                  <span>{summaryError}</span>
                  <Button variant="outline" size="xs" onClick={() => loadSummary(true)}>
                    Retry
                  </Button>
                </div>
              ) : summaryData ? (
                <div className="space-y-4">
                  {/* Synthesis Box */}
                  <div className="p-4 rounded-xl border border-border bg-panel/30 space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-[11px] font-semibold text-accent uppercase tracking-wider flex items-center gap-1.5">
                        <Sparkles className="w-3.5 h-3.5" />
                        Executive Overview & Synthesis
                      </span>
                      {summaryData.cached && (
                        <Badge variant="neutral" size="xs">
                          Cached In Tenant
                        </Badge>
                      )}
                    </div>
                    <p className="text-xs sm:text-sm text-primary leading-relaxed whitespace-pre-line select-text">
                      {summaryData.summary}
                    </p>
                  </div>

                  {/* Key Takeaways */}
                  <div className="space-y-2">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-secondary">
                      Core Takeaways & Findings
                    </h3>
                    {summaryData.key_takeaways && summaryData.key_takeaways.length > 0 ? (
                      <div className="space-y-2">
                        {summaryData.key_takeaways.map((takeaway, idx) => (
                          <div
                            key={idx}
                            className="p-3 rounded-lg border border-border bg-surface flex items-start gap-2.5 transition-colors"
                          >
                            <CheckCircle2 className="w-4 h-4 text-accent shrink-0 mt-0.5" />
                            <p className="text-xs text-primary leading-relaxed select-text">
                              {takeaway}
                            </p>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-xs text-secondary italic">
                        No individual bullet points synthesized. See narrative overview above.
                      </p>
                    )}
                  </div>
                </div>
              ) : null}
            </>
          )}

          {/* TAB 2: Provenance Chunks & Citations */}
          {activeTab === "citations" && (
            <div className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <div className="relative flex-1">
                  <Search className="w-3.5 h-3.5 text-secondary absolute left-3 top-1/2 -translate-y-1/2" />
                  <input
                    type="text"
                    value={chunkFilter}
                    onChange={(e) => setChunkFilter(e.target.value)}
                    placeholder="Filter chunks by keywords (e.g. 'indemnification', 'revenue', 'clause')..."
                    className="w-full bg-panel/50 border border-border rounded-lg pl-9 pr-3.5 py-1.5 text-xs text-primary placeholder:text-secondary focus:outline-none focus:border-accent"
                  />
                </div>
                <span className="text-xs text-secondary shrink-0 font-mono">
                  Showing {filteredChunks.length} of {chunks.length} chunks
                </span>
              </div>

              {loadingChunks ? (
                <div className="py-16 text-center space-y-2 text-secondary">
                  <RefreshCw className="w-5 h-5 text-accent animate-spin mx-auto" />
                  <p className="text-xs">Loading verified provenance chunks from database...</p>
                </div>
              ) : chunksError ? (
                <div className="p-4 rounded-lg bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-xs">
                  {chunksError}
                </div>
              ) : filteredChunks.length > 0 ? (
                <div className="space-y-2.5">
                  {filteredChunks.map((chunk, idx) => (
                    <div
                      key={chunk.id}
                      className="p-3.5 rounded-lg border border-border bg-panel/20 hover:bg-panel/40 transition-colors space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="inline-flex items-center px-1.5 py-0.5 rounded bg-accent/15 border border-accent/25 text-accent font-mono text-[10px] font-bold">
                            [S{chunk.chunk_index + 1}]
                          </span>
                          <span className="text-[11px] font-medium text-secondary font-mono">
                            Chunk #{chunk.chunk_index}
                          </span>
                          {chunk.page_number !== null && (
                            <span className="text-[11px] text-secondary font-mono">
                              • Page {chunk.page_number}
                            </span>
                          )}
                        </div>

                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => handleCopyChunk(chunk.id, chunk.content)}
                            className="p-1 rounded text-secondary hover:text-primary hover:bg-panel cursor-pointer text-xs flex items-center gap-1 transition-colors"
                            title="Copy chunk text"
                          >
                            {copiedChunkId === chunk.id ? (
                              <Check className="w-3.5 h-3.5 text-accent" />
                            ) : (
                              <Copy className="w-3.5 h-3.5" />
                            )}
                          </button>
                          <Button
                            variant="outline"
                            size="xs"
                            onClick={() =>
                              handleAskQuestion(
                                `Regarding [S${chunk.chunk_index + 1}] in ${document.original_filename || document.filename}: explain "${chunk.content.slice(0, 80)}..."`
                              )
                            }
                            className="text-[10px] h-6 px-1.5"
                          >
                            Inquire
                          </Button>
                        </div>
                      </div>

                      <p className="text-xs text-primary leading-relaxed whitespace-pre-wrap select-text font-sans">
                        {chunk.content}
                      </p>
                    </div>
                  ))}
                </div>
              ) : (
                <EmptyState
                  icon={<Layers className="w-5 h-5" />}
                  title="No chunks found"
                  description={
                    chunkFilter
                      ? `No chunks match "${chunkFilter}". Try a different keyword.`
                      : "Document does not have indexed chunks yet."
                  }
                />
              )}
            </div>
          )}

          {/* TAB 3: Related Inquiries */}
          {activeTab === "questions" && (
            <div className="space-y-3">
              <div className="p-3 rounded-lg bg-panel/30 border border-border">
                <p className="text-xs text-secondary leading-relaxed">
                  Select a targeted enterprise question to immediately query Cogniva with strict grounding in{" "}
                  <strong className="text-primary">{document.original_filename || document.filename}</strong>.
                </p>
              </div>

              <div className="space-y-2.5">
                {relatedQuestions.map((q, idx) => (
                  <div
                    key={idx}
                    className="p-3.5 rounded-lg border border-border bg-surface hover:bg-panel/40 transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-3 group"
                  >
                    <div className="space-y-1">
                      <span className="text-xs font-semibold text-primary group-hover:text-accent transition-colors flex items-center gap-1.5">
                        <HelpCircle className="w-3.5 h-3.5 text-accent shrink-0" />
                        {q.title}
                      </span>
                      <p className="text-xs text-secondary">{q.description}</p>
                      <p className="text-[11px] font-mono text-secondary/90 italic pt-0.5">
                        &quot;{q.prompt}&quot;
                      </p>
                    </div>

                    <Button
                      variant="primary"
                      size="xs"
                      onClick={() => handleAskQuestion(q.prompt)}
                      icon={<ArrowRight className="w-3.5 h-3.5" />}
                      className="shrink-0 self-start sm:self-center"
                    >
                      Ask Cogniva
                    </Button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* TAB 4: Extracted Units */}
          {activeTab === "raw" && (
            <div className="space-y-3">
              {loadingExtracted ? (
                <div className="py-16 text-center space-y-2 text-secondary">
                  <RefreshCw className="w-5 h-5 text-accent animate-spin mx-auto" />
                  <p className="text-xs">Loading page-aware extracted text units...</p>
                </div>
              ) : extracted && extracted.units.length > 0 ? (
                <div className="space-y-2">
                  <div className="flex items-center justify-between p-2.5 rounded-lg bg-panel/40 border border-border text-xs text-secondary font-mono">
                    <span>Format: <strong className="text-primary">{extracted.file_type.toUpperCase()}</strong></span>
                    <span>Units: <strong className="text-primary">{extracted.total_units}</strong></span>
                    <span>Words: <strong className="text-primary">{extracted.total_words.toLocaleString()}</strong></span>
                  </div>

                  <div className="space-y-2">
                    {extracted.units.map((unit) => (
                      <div
                        key={unit.sequence_number}
                        className="p-3 rounded-lg border border-border bg-panel/20 space-y-1.5"
                      >
                        <div className="flex items-center justify-between text-[10px] text-secondary font-mono">
                          <span className="font-semibold text-accent">
                            {unit.page_number !== null
                              ? `Page ${unit.page_number}`
                              : `Unit #${unit.sequence_number} (${unit.unit_type})`}
                          </span>
                          <span>Sequence {unit.sequence_number}</span>
                        </div>
                        <p className="text-xs text-primary leading-relaxed whitespace-pre-wrap select-text">
                          {unit.text}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <EmptyState
                  icon={<BookOpen className="w-5 h-5" />}
                  title="No raw units available"
                  description="Extracted units are generated during document parsing."
                />
              )}
            </div>
          )}
        </div>

        {/* Footer Bar */}
        <div className="px-5 py-3 border-t border-border bg-panel/40 flex items-center justify-between">
          <div className="flex items-center gap-2">
            {summaryData && (
              <Button
                variant="outline"
                size="xs"
                onClick={handleCopySummary}
                icon={copiedSummary ? <Check className="w-3.5 h-3.5 text-accent" /> : <Copy className="w-3.5 h-3.5" />}
              >
                {copiedSummary ? "Copied" : "Copy Takeaways"}
              </Button>
            )}
          </div>

          <Button variant="secondary" size="sm" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};

export default DocumentViewerModal;
