import React from "react";
import { Link } from "react-router-dom";
import {
  FileText,
  MessageSquare,
  Upload,
  Sparkles,
  ArrowRight,
  Shield,
  Layers,
} from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import { useDocuments } from "../hooks/useDocuments";
import EmptyState from "../components/common/EmptyState";
import Button from "../components/common/Button";
import Badge from "../components/common/Badge";

export const Dashboard: React.FC = () => {
  const { user } = useAuth();
  const { documents, isLoading: docsLoading } = useDocuments();

  return (
    <div className="space-y-6">
      {/* Welcome Banner */}
      <div className="bg-gradient-to-r from-indigo-900 via-indigo-800 to-purple-900 rounded-2xl p-6 sm:p-8 text-white shadow-sm flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
        <div>
          <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-white/10 text-white/90 text-xs font-medium mb-3 backdrop-blur-xs">
            <Sparkles className="w-3.5 h-3.5 text-indigo-300" />
            <span>Workspace Ready</span>
          </div>
          <h2 className="text-2xl sm:text-3xl font-bold tracking-tight">
            Welcome back, {user?.full_name || user?.email?.split("@")[0]}
          </h2>
          <p className="mt-1.5 text-sm text-indigo-100/90 max-w-xl leading-relaxed">
            Your Cogniva enterprise workspace is active. As documents are ingested, they will appear here with semantic indexing and source citations.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3 shrink-0">
          <Link to="/chat">
            <Button
              variant="outline"
              size="md"
              className="bg-white/10 hover:bg-white/20 text-white border-white/20"
              icon={<MessageSquare className="w-4 h-4" />}
            >
              Ask Cogniva
            </Button>
          </Link>
          <Link to="/documents">
            <Button
              variant="primary"
              size="md"
              className="bg-white text-indigo-900 hover:bg-slate-100 shadow-sm"
              icon={<Upload className="w-4 h-4" />}
            >
              Manage Documents
            </Button>
          </Link>
        </div>
      </div>

      {/* Main Grid: Recent Documents & Recent Conversations */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Documents Section */}
        <div className="bg-white border border-slate-200/90 rounded-2xl p-5 sm:p-6 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center text-indigo-600">
                  <FileText className="w-4 h-4" />
                </div>
                <h3 className="text-base font-semibold text-slate-900">
                  Recent Documents
                </h3>
              </div>
              <Link
                to="/documents"
                className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 flex items-center gap-1"
              >
                View all <ArrowRight className="w-3 h-3" />
              </Link>
            </div>

            {/* Real documents or genuine empty state */}
            {docsLoading ? (
              <div className="py-8 text-center text-xs text-slate-400">Loading documents...</div>
            ) : documents.length > 0 ? (
              <div className="space-y-2.5">
                {documents.slice(0, 3).map((doc) => {
                  const isPdf = doc.file_type.toLowerCase() === "pdf";
                  return (
                    <div
                      key={doc.id}
                      className="p-3 rounded-xl border border-slate-100 hover:border-slate-200 bg-slate-50/50 hover:bg-slate-50 transition-colors flex items-center justify-between gap-3"
                    >
                      <div className="flex items-center gap-2.5 truncate">
                        <div
                          className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${
                            isPdf
                              ? "bg-rose-50 text-rose-600 border border-rose-100"
                              : "bg-blue-50 text-blue-600 border border-blue-100"
                          }`}
                        >
                          <FileText className="w-3.5 h-3.5" />
                        </div>
                        <div className="truncate">
                          <p className="text-xs font-medium text-slate-900 truncate">
                            {doc.original_filename || doc.filename}
                          </p>
                          <p className="text-[10px] text-slate-400">
                            {new Date(doc.created_at).toLocaleDateString("en-US", {
                              month: "short",
                              day: "numeric",
                              year: "numeric",
                            })}
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
                          size="sm"
                        >
                          {doc.status}
                        </Badge>
                        <Badge variant={isPdf ? "danger" : "info"} size="sm">
                          {doc.file_type.toUpperCase()}
                        </Badge>
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <EmptyState
                icon={<FileText className="w-6 h-6 text-slate-400" />}
                title="No documents yet"
                description="Upload your first document to start asking Cogniva questions. Supported formats include PDF and DOCX."
                action={
                  <Link to="/documents">
                    <Button variant="outline" size="sm" icon={<Upload className="w-3.5 h-3.5" />}>
                      Upload Document
                    </Button>
                  </Link>
                }
              />
            )}
          </div>
        </div>

        {/* Recent Conversations Section */}
        <div className="bg-white border border-slate-200/90 rounded-2xl p-5 sm:p-6 shadow-xs flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-lg bg-purple-50 border border-purple-100 flex items-center justify-center text-purple-600">
                  <MessageSquare className="w-4 h-4" />
                </div>
                <h3 className="text-base font-semibold text-slate-900">
                  Recent Conversations
                </h3>
              </div>
              <Link
                to="/chat"
                className="text-xs font-semibold text-indigo-600 hover:text-indigo-700 flex items-center gap-1"
              >
                Start chat <ArrowRight className="w-3 h-3" />
              </Link>
            </div>

            {/* Empty state (No fake data!) */}
            <EmptyState
              icon={<MessageSquare className="w-6 h-6 text-slate-400" />}
              title="No conversations yet"
              description="Start a new session to query your enterprise knowledge with source-grounded answers."
              action={
                <Link to="/chat">
                  <Button variant="primary" size="sm" icon={<MessageSquare className="w-3.5 h-3.5" />}>
                    New Conversation
                  </Button>
                </Link>
              }
            />
          </div>
        </div>
      </div>

      {/* Platform Architecture Status (Transparent & Accurate) */}
      <div className="bg-white border border-slate-200/90 rounded-2xl p-5 sm:p-6 shadow-xs">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3">
          Platform Foundation Status
        </h4>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-100">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-800">
              <Shield className="w-4 h-4 text-emerald-600 shrink-0" />
              Authentication & Security
            </div>
            <p className="text-[11px] text-slate-500 mt-1">
              Active: Session secured with JWT & bcrypt (Phase 3)
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-100">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-800">
              <Layers className="w-4 h-4 text-indigo-600 shrink-0" />
              Database & Vector Layer
            </div>
            <p className="text-[11px] text-slate-500 mt-1">
              Active: PostgreSQL 16 + pgvector schema ready (Phase 2)
            </p>
          </div>

          <div className="p-3.5 rounded-xl bg-slate-50 border border-slate-100">
            <div className="flex items-center gap-2 text-xs font-semibold text-slate-800">
              <Sparkles className="w-4 h-4 text-amber-600 shrink-0" />
              Document Ingestion (Phase 5)
            </div>
            <p className="text-[11px] text-slate-500 mt-1">
              Next: High-fidelity document parsing & chunking pipeline
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
