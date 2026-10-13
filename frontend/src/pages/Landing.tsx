import React from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  ShieldCheck,
  FileSearch,
  Layers,
  Database,
  CheckCircle2,
} from "lucide-react";
import { useAuth } from "../hooks/useAuth";
import ThemeToggle from "../components/common/ThemeToggle";

export const Landing: React.FC = () => {
  const { isAuthenticated } = useAuth();

  const capabilities = [
    {
      icon: <FileSearch className="w-5 h-5 text-accent" />,
      title: "Deterministic Ingestion",
      desc: "High-fidelity extraction over PDFs and Word (.docx) documents preserving page numbers, structure, and metadata.",
    },
    {
      icon: <Database className="w-5 h-5 text-accent" />,
      title: "Native pgvector Retrieval",
      desc: "1536-dimensional dense embeddings indexed natively in PostgreSQL with strict SQL-level tenant isolation.",
    },
    {
      icon: <ShieldCheck className="w-5 h-5 text-accent" />,
      title: "Verifiable Source Provenance",
      desc: "Every claim cites response-scoped identifiers ([S1], [S2]) linking directly to verifiable database chunk excerpts.",
    },
    {
      icon: <Layers className="w-5 h-5 text-accent" />,
      title: "Multi-Turn Conversation Threads",
      desc: "Persistent chat history surviving refreshes and reboots with bounded context and query enrichment.",
    },
  ];

  return (
    <div className="min-h-screen bg-canvas text-primary flex flex-col font-sans transition-colors">
      {/* Navigation Bar */}
      <header className="border-b border-border bg-surface sticky top-0 z-50 transition-colors">
        <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-md bg-[#267653] dark:bg-[#42B883] text-white dark:text-[#121614] flex items-center justify-center font-bold text-sm shadow-xs">
              <Layers className="w-4 h-4" />
            </div>
            <div>
              <span className="text-sm font-bold tracking-wide uppercase text-primary">
                Cogniva
              </span>
              <span className="hidden sm:inline-block ml-2 text-xs text-secondary font-normal">
                Enterprise Knowledge Platform
              </span>
            </div>
          </Link>

          <div className="flex items-center gap-3">
            <ThemeToggle compact />

            {isAuthenticated ? (
              <Link
                to="/dashboard"
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#267653] dark:bg-[#42B883] hover:bg-[#1E5D42] dark:hover:bg-[#36996D] text-white dark:text-[#121614] text-xs font-semibold shadow-xs transition-colors"
              >
                Go to Workspace
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            ) : (
              <>
                <Link
                  to="/login"
                  className="px-3 py-1.5 rounded-lg text-xs font-semibold text-secondary hover:text-primary hover:bg-panel transition-colors"
                >
                  Sign In
                </Link>
                <Link
                  to="/register"
                  className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg bg-[#267653] dark:bg-[#42B883] hover:bg-[#1E5D42] dark:hover:bg-[#36996D] text-white dark:text-[#121614] text-xs font-semibold shadow-xs transition-colors"
                >
                  Get Started
                  <ArrowRight className="w-3.5 h-3.5" />
                </Link>
              </>
            )}
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="pt-16 sm:pt-20 pb-12 px-4 sm:px-6 lg:px-8 max-w-4xl mx-auto text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-panel border border-border text-xs font-medium text-secondary mb-6">
          <span className="w-2 h-2 rounded-full bg-accent" />
          Grounded Multimodal Enterprise Knowledge Platform
        </div>

        <h1 className="text-3xl sm:text-5xl font-bold tracking-tight text-primary leading-tight mb-4">
          Understand. Retrieve. <br />
          <span className="text-accent">Analyze. Act.</span>
        </h1>

        <p className="text-xs sm:text-sm text-secondary max-w-2xl mx-auto mb-8 leading-relaxed">
          Cogniva ingests enterprise PDFs and Word documents, computes deterministic vector embeddings, and generates strictly grounded answers backed by authentic, verifiable page citations.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-3">
          <Link
            to={isAuthenticated ? "/dashboard" : "/register"}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-[#267653] dark:bg-[#42B883] hover:bg-[#1E5D42] dark:hover:bg-[#36996D] text-white dark:text-[#121614] text-xs font-semibold shadow-xs transition-colors"
          >
            {isAuthenticated ? "Enter Workspace" : "Deploy Enterprise Account"}
            <ArrowRight className="w-4 h-4" />
          </Link>
          <Link
            to="/login"
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-lg bg-surface border border-border hover:bg-panel text-primary text-xs font-medium transition-colors"
          >
            Existing Tenant Login
          </Link>
        </div>
      </section>

      {/* Capabilities Section */}
      <section className="py-12 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto w-full">
        <div className="border-b border-border pb-3 mb-6">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-secondary">
            Core Enterprise Capabilities
          </h2>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {capabilities.map((cap, i) => (
            <div
              key={i}
              className="p-5 rounded-xl border border-border bg-surface hover:bg-panel/50 transition-colors"
            >
              <div className="w-8 h-8 rounded-lg bg-panel border border-border flex items-center justify-center mb-3">
                {cap.icon}
              </div>
              <h3 className="text-xs sm:text-sm font-semibold text-primary mb-1">
                {cap.title}
              </h3>
              <p className="text-xs text-secondary leading-relaxed">
                {cap.desc}
              </p>
            </div>
          ))}
        </div>
      </section>

      {/* Architectural Guarantees */}
      <section className="py-8 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto w-full">
        <div className="p-5 rounded-xl border border-border bg-panel/30 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <div>
            <h4 className="text-xs font-semibold text-primary uppercase tracking-wider">
              Deterministic Security & Anti-Injection
            </h4>
            <p className="text-xs text-secondary mt-1">
              Untrusted document context is partitioned behind strict boundary markers. Unverified hallucinations are rejected.
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0 text-xs text-accent font-medium">
            <CheckCircle2 className="w-4 h-4 text-accent" />
            <span>Zero Cross-Tenant Leakage</span>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-auto border-t border-border bg-surface py-6 text-center text-xs text-secondary transition-colors">
        <div className="max-w-6xl mx-auto px-4 flex flex-col sm:flex-row items-center justify-between gap-2">
          <span className="font-medium text-primary">Cogniva Enterprise</span>
          <span>Understand. Retrieve. Analyze. Act.</span>
          <span className="font-mono text-[11px]">PostgreSQL 16 · pgvector · FastAPI</span>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
