import React, { useState } from "react";
import { Plus, MessageSquare, Trash2, Check, X, Loader2, Sparkles } from "lucide-react";
import { ConversationResponse } from "../../types/chat";

interface ConversationSidebarProps {
  conversations: ConversationResponse[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  onDelete: (id: string) => Promise<void>;
  loading: boolean;
  isOpen: boolean;
  onClose: () => void;
}

export const ConversationSidebar: React.FC<ConversationSidebarProps> = ({
  conversations,
  activeId,
  onSelect,
  onNewChat,
  onDelete,
  loading,
  isOpen,
  onClose,
}) => {
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const handleDeleteClick = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    setConfirmDeleteId(id);
  };

  const handleConfirmDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    try {
      setDeletingId(id);
      await onDelete(id);
    } finally {
      setDeletingId(null);
      setConfirmDeleteId(null);
    }
  };

  const handleCancelDelete = (e: React.MouseEvent) => {
    e.stopPropagation();
    setConfirmDeleteId(null);
  };

  const formatTimestamp = (dateStr: string) => {
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMins / 60);
    const diffDays = Math.floor(diffHours / 24);

    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays === 1) return "Yesterday";
    if (diffDays < 7) return `${diffDays}d ago`;
    return d.toLocaleDateString([], { month: "short", day: "numeric" });
  };

  const sidebarContent = (
    <div className="flex flex-col h-full bg-slate-50 border-r border-slate-200/90 w-72 shrink-0">
      {/* Top Action Header */}
      <div className="p-3.5 border-b border-slate-200/80 bg-white">
        <button
          onClick={() => {
            onNewChat();
            onClose();
          }}
          className="w-full flex items-center justify-center gap-2 px-3.5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold shadow-xs transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span>New Chat</span>
        </button>
      </div>

      {/* Conversations Section Header */}
      <div className="px-4 py-2.5 flex items-center justify-between text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
        <span>History</span>
        <span className="bg-slate-200/80 text-slate-600 px-1.5 py-0.5 rounded text-[10px] font-medium">
          {conversations.length}
        </span>
      </div>

      {/* Conversation Item List */}
      <div className="flex-1 overflow-y-auto px-2 pb-4 space-y-1">
        {loading ? (
          <div className="p-6 text-center text-slate-400 text-xs flex flex-col items-center justify-center gap-2">
            <Loader2 className="w-5 h-5 animate-spin text-indigo-600" />
            <span>Loading conversations...</span>
          </div>
        ) : conversations.length === 0 ? (
          <div className="p-6 text-center text-slate-400 text-xs">
            <MessageSquare className="w-6 h-6 mx-auto mb-2 text-slate-300" />
            <p className="font-medium text-slate-600">No chats yet</p>
            <p className="text-[11px] text-slate-400 mt-1">
              Ask questions to start and persist conversations.
            </p>
          </div>
        ) : (
          conversations.map((conv) => {
            const isActive = conv.id === activeId;
            const isConfirming = confirmDeleteId === conv.id;
            const isDeleting = deletingId === conv.id;

            return (
              <div
                key={conv.id}
                onClick={() => {
                  if (!isConfirming && !isDeleting) {
                    onSelect(conv.id);
                    onClose();
                  }
                }}
                className={`group relative flex items-center justify-between px-3 py-2.5 rounded-xl text-xs cursor-pointer transition-colors ${
                  isActive
                    ? "bg-indigo-50 border border-indigo-200/80 text-indigo-950 font-medium"
                    : "text-slate-700 hover:bg-white hover:text-slate-900 border border-transparent"
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0 flex-1 pr-2">
                  <div
                    className={`w-6 h-6 rounded-md flex items-center justify-center shrink-0 ${
                      isActive
                        ? "bg-indigo-600 text-white"
                        : "bg-slate-200 text-slate-500 group-hover:bg-slate-300"
                    }`}
                  >
                    <MessageSquare className="w-3.5 h-3.5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-xs leading-snug">{conv.title}</p>
                    <p className="text-[10px] text-slate-400 mt-0.5">
                      {formatTimestamp(conv.updated_at)}
                    </p>
                  </div>
                </div>

                {/* Actions: Normal or Confirm Delete */}
                <div className="shrink-0 flex items-center">
                  {isConfirming ? (
                    <div className="flex items-center gap-1 bg-white border border-rose-200 rounded-lg p-0.5 shadow-xs">
                      <button
                        onClick={(e) => handleConfirmDelete(e, conv.id)}
                        disabled={isDeleting}
                        title="Confirm Delete"
                        className="p-1 rounded text-rose-600 hover:bg-rose-50 transition-colors"
                      >
                        {isDeleting ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Check className="w-3.5 h-3.5" />
                        )}
                      </button>
                      <button
                        onClick={handleCancelDelete}
                        disabled={isDeleting}
                        title="Cancel"
                        className="p-1 rounded text-slate-400 hover:bg-slate-100 transition-colors"
                      >
                        <X className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={(e) => handleDeleteClick(e, conv.id)}
                      title="Delete chat"
                      className="opacity-0 group-hover:opacity-100 p-1 rounded-md text-slate-400 hover:text-rose-600 hover:bg-rose-50 transition-all"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Footer System Status */}
      <div className="p-3 border-t border-slate-200/80 bg-white text-[11px] text-slate-500 flex items-center gap-2">
        <Sparkles className="w-3.5 h-3.5 text-indigo-500 shrink-0" />
        <span className="truncate">Persistent PostgreSQL storage</span>
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop sidebar */}
      <div className="hidden md:flex h-full">{sidebarContent}</div>

      {/* Mobile drawer backdrop and overlay */}
      {isOpen && (
        <div className="fixed inset-0 z-50 md:hidden flex">
          <div
            className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs transition-opacity"
            onClick={onClose}
          />
          <div className="relative z-10 h-full shadow-2xl flex">{sidebarContent}</div>
        </div>
      )}
    </>
  );
};

export default ConversationSidebar;
