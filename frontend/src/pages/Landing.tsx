import React from "react";
import { Link } from "react-router-dom";
import {
  Sparkles,
  ArrowRight,
  ShieldCheck,
  FileSearch,
  Layers,
  Database,
  CheckCircle2,
} from "lucide-react";
import { useAuth } from "../hooks/useAuth";

export const Landing: React.FC = () => {
  const { isAuthenticated } = useAuth();

  const capabilities = [
    {
      icon: <FileSearch className="w-5 h-5 text-indigo-600" />,
      title: "Heterogeneous Ingestion",
      desc: "Engineered to ingest PDFs, DOCX documents, spreadsheets, and complex enterprise assets with layout fidelity.",
    },
    {
      icon: <Database className="w-5 h-5 text-purple-600" />,
      title: "Hybrid Semantic Retrieval",
      desc: "Combines dense vector embeddings with full-text keyword indexing and re-ranking for ultra-high recall.",
    },
    {
      icon: <ShieldCheck className="w-5 h-5 text-emerald-600" />,
      title: "Strictly Grounded Answers",
      desc: "Every answer is backed by verifiable citations directly pointing to source files and page numbers.",
    },
    {
      icon: <Layers className="w-5 h-5 text-blue-600" />,
      title: "Autonomous Agents",
      desc: "Coordinates multi-step analysis, comparative cross-document reasoning, and synthesis workflows.",
    },
  ];

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col font-sans text-slate-900 selection:bg-indigo-100 selection:text-indigo-900">
      {/* Navigation Bar */}
      <header className="border-b border-slate-200/80 bg-white/80 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3 group">
            <div className="w-9 h-9 rounded-xl bg-gradient-to-tr from-indigo-600 to-purple-600 flex items-center justify-center text-white shadow-xs group-hover:scale-105 transition-transform">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <span className="text-lg font-bold tracking-tight text-slate-900">
                Cogniva
              </span>
              <span className="hidden sm:inline-block ml-2 text-xs text-slate-400 font-normal">
                Enterprise Knowledge Agent
              </span>
            </div>
          </Link>

          <div className="flex items-center gap-3">
            {isAuthenticated ? (
              <Link
                to="/dashboard"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-xs transition-colors"
              >
                Go to Dashboard
                <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            ) : (
              <>
                <Link
                  to="/login"
                  className="px-3.5 py-2 rounded-lg text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors"
                >
                  Sign In
                </Link>
                <Link
                  to="/register"
                  className="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-xs transition-colors"
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
      <section className="relative pt-16 sm:pt-24 pb-16 px-4 sm:px-6 lg:px-8 max-w-5xl mx-auto text-center">
        <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-indigo-50 border border-indigo-200/80 text-xs font-semibold text-indigo-700 mb-6">
          <span className="w-2 h-2 rounded-full bg-indigo-600 animate-pulse" />
          Multimodal Enterprise Knowledge Platform
        </div>

        <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-slate-900 leading-[1.15] mb-6">
          Understand. Retrieve. <br className="hidden sm:block" />
          <span className="bg-gradient-to-r from-indigo-600 via-indigo-700 to-purple-600 bg-clip-text text-transparent">
            Analyze. Act.
          </span>
        </h1>

        <p className="text-lg sm:text-xl text-slate-600 max-w-2xl mx-auto mb-10 leading-relaxed font-normal">
          Cogniva is the intelligent knowledge agent built for modern organizations. Ingest complex documents, run verified semantic queries, and eliminate hallucinations with source-grounded answers.
        </p>

        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 max-w-sm mx-auto mb-12">
          <Link
            to={isAuthenticated ? "/dashboard" : "/register"}
            className="w-full sm:w-auto inline-flex items-center justify-center gap-2 px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-medium text-sm shadow-md hover:shadow-lg transition-all"
          >
            {isAuthenticated ? "Enter Workspace" : "Start Free Evaluation"}
            <ArrowRight className="w-4 h-4" />
          </Link>
          <Link
            to={isAuthenticated ? "/chat" : "/login"}
            className="w-full sm:w-auto inline-flex items-center justify-center px-5 py-3 rounded-xl bg-white border border-slate-300 hover:bg-slate-50 text-slate-700 font-medium text-sm transition-colors"
          >
            {isAuthenticated ? "Open Ask Cogniva" : "Sign In to Account"}
          </Link>
        </div>

        {/* Enterprise trust badges */}
        <div className="flex flex-wrap items-center justify-center gap-6 text-xs text-slate-500 pt-4 border-t border-slate-200/60 max-w-xl mx-auto">
          <span className="flex items-center gap-1.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" /> PostgreSQL + pgvector
          </span>
          <span className="flex items-center gap-1.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" /> Enterprise Role-Based Access
          </span>
          <span className="flex items-center gap-1.5">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" /> Zero Hallucination Mode
          </span>
        </div>
      </section>

      {/* Architectural Capabilities */}
      <section className="py-16 bg-white border-y border-slate-200/80 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center max-w-2xl mx-auto mb-12">
            <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight">
              Engineered for Mission-Critical Accuracy
            </h2>
            <p className="text-sm text-slate-500 mt-2">
              Unlike generic chat assistants, Cogniva enforces strict provenance, verifiable source citations, and deterministic retrieval pipelines.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {capabilities.map((c, i) => (
              <div
                key={i}
                className="p-6 rounded-2xl bg-slate-50 border border-slate-200/80 hover:border-slate-300 transition-all hover:shadow-xs flex flex-col justify-between"
              >
                <div>
                  <div className="w-10 h-10 rounded-xl bg-white border border-slate-200 flex items-center justify-center mb-4 shadow-xs">
                    {c.icon}
                  </div>
                  <h3 className="text-base font-semibold text-slate-900 mb-2">
                    {c.title}
                  </h3>
                  <p className="text-xs text-slate-600 leading-relaxed font-normal">
                    {c.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-auto py-8 bg-slate-50 border-t border-slate-200/80 text-center text-xs text-slate-400">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-slate-700">Cogniva Platform</span>
            <span>—</span>
            <span>Understand. Retrieve. Analyze. Act.</span>
          </div>
          <p>© {new Date().getFullYear()} Cogniva Inc. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
};

export default Landing;
