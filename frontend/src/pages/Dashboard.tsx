import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  FileText,
  MessageSquare,
  Upload,
  ArrowRight,
  Shield,
  Layers,
  CheckCircle2,
  HardDrive,
  Clock,
  Activity,
  AlertCircle,
} from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { useDocuments } from "../hooks/useDocuments";
import { listConversations } from "../services/chatService";
import { checkHealth, HealthResponse } from "../services/api";
import { ConversationResponse } from "../types/chat";
import EmptyState from "../components/common/EmptyState";
import Button from "../components/common/Button";
import Badge from "../components/common/Badge";

export const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const { documents, isLoading: docsLoading } = useDocuments();

  const [conversations, setConversations] = useState<ConversationResponse[]>([]);
  const [convsLoading, setConvsLoading] = useState<boolean>(true);
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    const loadConversations = async () => {
      try {
        setConvsLoading(true);
        const res = await listConversations(0, 5);
        if (isMounted) {
          setConversations(res.items || []);
        }
      } catch {
        if (isMounted) setConversations([]);
      } finally {
        if (isMounted) setConvsLoading(false);
      }
    };

    const loadHealth = async () => {
      try {
        const res = await checkHealth();
        if (isMounted) {
          setHealth(res);
          setHealthError(null);
        }
      } catch (err: any) {
        if (isMounted) {
          setHealthError("API service unreachable");
        }
      }
    };

    loadConversations();
    loadHealth();

    return () => {
      isMounted = false;
    };
  }, []);

  // Compute real metrics from loaded documents
  const totalDocs = documents.length;
  const processedDocs = documents.filter((d) => d.status === "processed").length;
  const pendingDocs = documents.filter((d) => d.status === "processing" || d.status === "pending").length;
  const failedDocs = documents.filter((d) => d.status === "failed").length;

  const totalBytes = documents.reduce((acc, doc) => acc + (doc.metadata?.size_bytes || 0), 0);
  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return "0 KB";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="space-y-6">
      {/* Workspace Header Panel */}
      <div className="bg-surface border border-border rounded-xl p-5 sm:p-6 transition-colors">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-semibold text-accent uppercase tracking-wider">
                Enterprise Workspace
              </span>
              <span className="text-secondary text-xs">•</span>
              <span className="text-xs text-secondary font-mono">{user?.email}</span>
            </div>
            <h2 className="text-xl sm:text-2xl font-bold tracking-tight text-primary">
              Welcome, {user?.full_name || user?.email?.split("@")[0]}
            </h2>
            <p className="mt-1 text-xs sm:text-sm text-secondary max-w-2xl leading-relaxed">
              Cogniva knowledge workspace is active with isolated tenant boundaries. Ingest enterprise documents to index semantic chunks and execute source-grounded intelligence queries.
            </p>
          </div>

          <div className="flex items-center gap-2.5 shrink-0">
            <Link to="/chat">
              <Button
                variant="outline"
                size="sm"
                icon={<MessageSquare className="w-4 h-4" />}
              >
                Ask Cogniva
              </Button>
            </Link>
            <Link to="/documents">
              <Button
                variant="primary"
                size="sm"
                icon={<Upload className="w-4 h-4" />}
              >
                Upload Document
              </Button>
            </Link>
          </div>
        </div>
      </div>

      {/* Real Workspace Telemetry Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Metric 1: Total Documents */}
        <div className="bg-surface border border-border rounded-xl p-4 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-secondary">Indexed Documents</span>
            <FileText className="w-4 h-4 text-secondary" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-primary">{totalDocs}</span>
            <span className="text-xs text-secondary">files</span>
          </div>
          <p className="mt-1 text-[11px] text-secondary">
            {processedDocs} ready for retrieval
          </p>
        </div>

        {/* Metric 2: Processing Status */}
        <div className="bg-surface border border-border rounded-xl p-4 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-secondary">Pipeline Status</span>
            <Layers className="w-4 h-4 text-secondary" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-primary">
              {failedDocs > 0 ? `${failedDocs} Failed` : pendingDocs > 0 ? `${pendingDocs} Pending` : "100%"}
            </span>
          </div>
          <p className="mt-1 text-[11px] text-secondary">
            {pendingDocs > 0 ? "Chunks undergoing ingestion" : "All assets processed"}
          </p>
        </div>

        {/* Metric 3: Active Conversations */}
        <div className="bg-surface border border-border rounded-xl p-4 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-secondary">Active Threads</span>
            <MessageSquare className="w-4 h-4 text-secondary" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-primary">{conversations.length}</span>
            <span className="text-xs text-secondary">sessions</span>
          </div>
          <p className="mt-1 text-[11px] text-secondary">
            Persistent multi-turn history
          </p>
        </div>

        {/* Metric 4: Knowledge Footprint */}
        <div className="bg-surface border border-border rounded-xl p-4 transition-colors">
          <div className="flex items-center justify-between">
            <span className="text-xs font-medium text-secondary">Knowledge Footprint</span>
            <HardDrive className="w-4 h-4 text-secondary" />
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-primary">{formatBytes(totalBytes)}</span>
          </div>
          <p className="mt-1 text-[11px] text-secondary">
            PDF & Word storage in tenant pool
          </p>
        </div>
      </div>

      {/* Main Grid: Recent Documents & Recent Conversations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Documents Section */}
        <div className="bg-surface border border-border rounded-xl p-5 transition-colors flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-border">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-accent" />
                <h3 className="text-sm font-semibold text-primary">
                  Recent Knowledge Sources
                </h3>
              </div>
              <Link
                to="/documents"
                className="text-xs font-medium text-accent hover:underline flex items-center gap-1"
              >
                View all ({totalDocs}) <ArrowRight className="w-3 h-3" />
              </Link>
            </div>

            {docsLoading ? (
              <div className="py-8 text-center text-xs text-secondary">Loading document repository...</div>
            ) : documents.length > 0 ? (
              <div className="space-y-2">
                {documents.slice(0, 4).map((doc) => {
                  const isPdf = doc.file_type.toLowerCase() === "pdf";
                  return (
                    <div
                      key={doc.id}
                      className="p-3 rounded-lg border border-border bg-panel/40 hover:bg-panel transition-colors flex items-center justify-between gap-3"
                    >
                      <div className="flex items-center gap-2.5 truncate">
                        <div className="w-7 h-7 rounded bg-surface border border-border flex items-center justify-center shrink-0 text-secondary">
                          <FileText className="w-3.5 h-3.5" />
                        </div>
                        <div className="truncate">
                          <p className="text-xs font-medium text-primary truncate">
                            {doc.original_filename || doc.filename}
                          </p>
                          <p className="text-[10px] text-secondary">
                            {new Date(doc.created_at).toLocaleDateString("en-US", {
                              month: "short",
                              day: "numeric",
                              year: "numeric",
                            })} · {formatBytes(doc.metadata?.size_bytes || 0)}
                          </p>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
                        <Badge
                          variant={
                            doc.status === "processed"
                              ? "success"
                              : doc.status === "failed"
                              ? "danger"
                              : "secondary"
                          }
                          size="xs"
                        >
                          {doc.status}
                        </Badge>
                        <Badge variant="neutral" size="xs">
                          {doc.file_type.toUpperCase()}
                        </Badge>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <EmptyState
                icon={<FileText className="w-5 h-5" />}
                title="No documents uploaded"
                description="Upload enterprise documentation (PDF or DOCX) to index semantic chunks."
                action={
                  <Link to="/documents">
                    <Button variant="outline" size="xs" icon={<Upload className="w-3 h-3" />}>
                      Upload Document
                    </Button>
                  </Link>
                }
              />
            )}
          </div>
        </div>

        {/* Recent Conversations Section */}
        <div className="bg-surface border border-border rounded-xl p-5 transition-colors flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4 pb-3 border-b border-border">
              <div className="flex items-center gap-2">
                <MessageSquare className="w-4 h-4 text-accent" />
                <h3 className="text-sm font-semibold text-primary">
                  Recent Inquiries
                </h3>
              </div>
              <Link
                to="/chat"
                className="text-xs font-medium text-accent hover:underline flex items-center gap-1"
              >
                Open Chat <ArrowRight className="w-3 h-3" />
              </Link>
            </div>

            {convsLoading ? (
              <div className="py-8 text-center text-xs text-secondary">Loading conversations...</div>
            ) : conversations.length > 0 ? (
              <div className="space-y-2">
                {conversations.slice(0, 4).map((conv) => (
                  <Link
                    key={conv.id}
                    to={`/chat/${conv.id}`}
                    className="p-3 rounded-lg border border-border bg-panel/40 hover:bg-panel transition-colors flex items-center justify-between gap-3 block group"
                  >
                    <div className="flex items-center gap-2.5 truncate">
                      <div className="w-7 h-7 rounded bg-surface border border-border flex items-center justify-center shrink-0 text-secondary">
                        <MessageSquare className="w-3.5 h-3.5" />
                      </div>
                      <div className="truncate">
                        <p className="text-xs font-medium text-primary group-hover:text-accent truncate">
                          {conv.title || "Untitled Session"}
                        </p>
                        <p className="text-[10px] text-secondary flex items-center gap-1">
                          <Clock className="w-2.5 h-2.5" />
                          {new Date(conv.updated_at || conv.created_at).toLocaleDateString("en-US", {
                            month: "short",
                            day: "numeric",
                            hour: "2-digit",
                            minute: "2-digit",
                          })}
                        </p>
                      </div>
                    </div>
                    <ArrowRight className="w-3.5 h-3.5 text-secondary group-hover:text-primary shrink-0" />
                  </Link>
                ))}
              </div>
            ) : (
              <EmptyState
                icon={<MessageSquare className="w-5 h-5" />}
                title="No chat sessions yet"
                description="Initiate a query to receive strictly grounded answers with verifiable source citations."
                action={
                  <Link to="/chat">
                    <Button variant="primary" size="xs" icon={<MessageSquare className="w-3 h-3" />}>
                      Start Inquiry
                    </Button>
                  </Link>
                }
              />
            )}
          </div>
        </div>
      </div>

      {/* Real System Architecture & Platform Telemetry Status */}
      <div className="bg-surface border border-border rounded-xl p-5 transition-colors">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-secondary">
            Platform Service Infrastructure
          </h4>
          <span className="text-[11px] text-secondary font-mono">
            Environment: {health?.environment || "production"}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {/* Card 1: API Gateway Status */}
          <div className="p-3.5 rounded-lg bg-panel/50 border border-border">
            <div className="flex items-center justify-between text-xs font-semibold text-primary">
              <span className="flex items-center gap-1.5">
                <Activity className="w-3.5 h-3.5 text-accent" />
                API Service Gateway
              </span>
              <Badge variant={health ? "success" : "warning"} size="xs">
                {health ? "Operational" : healthError || "Connecting"}
              </Badge>
            </div>
            <p className="text-[11px] text-secondary mt-1.5">
              FastAPI ASGI service v{health?.version || "0.1.0"} with CORS & JWT enforcement.
            </p>
          </div>

          {/* Card 2: Vector Engine */}
          <div className="p-3.5 rounded-lg bg-panel/50 border border-border">
            <div className="flex items-center justify-between text-xs font-semibold text-primary">
              <span className="flex items-center gap-1.5">
                <Layers className="w-3.5 h-3.5 text-accent" />
                PostgreSQL + pgvector
              </span>
              <Badge variant="success" size="xs">
                Active
              </Badge>
            </div>
            <p className="text-[11px] text-secondary mt-1.5">
              Cosine distance index (`&lt;=&gt;`) with database-enforced tenant isolation.
            </p>
          </div>

          {/* Card 3: RAG Grounding Engine */}
          <div className="p-3.5 rounded-lg bg-panel/50 border border-border">
            <div className="flex items-center justify-between text-xs font-semibold text-primary">
              <span className="flex items-center gap-1.5">
                <Shield className="w-3.5 h-3.5 text-accent" />
                Citation Verification
              </span>
              <Badge variant="success" size="xs">
                Enforced
              </Badge>
            </div>
            <p className="text-[11px] text-secondary mt-1.5">
              Prompt injection boundaries & rejection of unreferenced hallucinated sources.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
