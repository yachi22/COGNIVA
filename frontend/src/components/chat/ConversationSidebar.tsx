import React, { useState } from "react";
import { Plus, MessageSquare, Trash2, Check, X, Loader2, Search } from "lucide-react";
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
  const [searchTerm, setSearchTerm] = useState("");
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);

  const filteredConversations = conversations.filter((c) =>
    (c.title || "Untitled Session").toLowerCase().includes(searchTerm.toLowerCase())
  );

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
    try {
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
    } catch {
      return dateStr;
    }
  };

  const sidebarContent = (
    <div className="flex flex-col h-full bg-surface border-r border-border w-72 shrink-0 transition-colors">
      {/* Top Action Header */}
      <div className="p-3 border-b border-border bg-panel/30 space-y-2">
        <button
          onClick={() => {
            onNewChat();
            onClose();
          }}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 rounded-lg bg-[#267653] dark:bg-[#42B883] hover:bg-[#1E5D42] dark:hover:bg-[#36996D] text-white dark:text-[#121614] text-xs font-semibold shadow-xs transition-colors cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          <span>New Inquiry</span>
        </button>

        {/* Search threads */}
        {conversations.length > 5 && (
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-secondary absolute left-2.5 top-2.5" />
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="Search conversations..."
              className="w-full pl-8 pr-2.5 py-1.5 text-xs bg-surface border border-border rounded-md text-primary placeholder:text-secondary/70 focus:outline-none focus:border-accent"
            />
          </div>
        )}
      </div>

      {/* Conversations Section Header */}
      <div className="px-3 py-2 flex items-center justify-between text-[10px] font-semibold text-secondary uppercase tracking-wider">
        <span>Conversation History</span>
        <span className="bg-panel text-secondary px-1.5 py-0.2 rounded text-[10px] font-mono">
          {conversations.length}
        </span>
      </div>

      {/* Conversation Item List */}
      <div className="flex-1 overflow-y-auto px-2 pb-3 space-y-1">
        {loading ? (
          <div className="p-6 text-center text-secondary text-xs flex flex-col items-center justify-center gap-2">
            <Loader2 className="w-4 h-4 animate-spin text-accent" />
            <span>Loading history...</span>
          </div>
        ) : filteredConversations.length === 0 ? (
          <div className="p-6 text-center text-secondary text-xs">
            <MessageSquare className="w-5 h-5 mx-auto mb-2 text-secondary/50" />
            <p className="font-medium text-primary">
              {searchTerm ? "No matching chats" : "No past sessions"}
            </p>
            <p className="text-[11px] text-secondary mt-1">
              {searchTerm ? "Try another search" : "Your queries will be logged here"}
            </p>
          </div>
        ) : (
          filteredConversations.map((c) => {
            const isActive = activeId === c.id;
            const isConfirming = confirmDeleteId === c.id;
            const isDeleting = deletingId === c.id;

            return (
              <div
                key={c.id}
                onClick={() => {
                  onSelect(c.id);
                  onClose();
                }}
                className={`group relative flex items-center justify-between p-2.5 rounded-lg text-xs transition-colors cursor-pointer ${
                  isActive
                    ? "bg-panel text-primary font-medium border-l-2 border-accent"
                    : "text-secondary hover:text-primary hover:bg-panel/50"
                }`}
              >
                <div className="flex items-start gap-2.5 min-w-0 pr-1">
                  <MessageSquare className={`w-3.5 h-3.5 mt-0.5 shrink-0 ${isActive ? "text-accent" : "text-secondary"}`} />
                  <div className="min-w-0">
                    <p className={`truncate leading-snug ${isActive ? "text-primary font-medium" : "text-primary/90"}`}>
                      {c.title || "Untitled Session"}
                    </p>
                    <p className="text-[10px] text-secondary mt-0.5">
                      {formatTimestamp(c.updated_at || c.created_at)}
                    </p>
                  </div>
                </div>

                {/* Delete / Confirmation Actions */}
                <div className="shrink-0 flex items-center">
                  {isConfirming ? (
                    <div className="flex items-center gap-1 bg-surface border border-border rounded p-0.5">
                      <button
                        onClick={(e) => handleConfirmDelete(e, c.id)}
                        disabled={isDeleting}
                        title="Confirm deletion"
                        className="p-1 rounded text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/40 transition-colors"
                      >
                        {isDeleting ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <Check className="w-3 h-3" />
                        )}
                      </button>
                      <button
                        onClick={handleCancelDelete}
                        title="Cancel"
                        className="p-1 rounded text-secondary hover:bg-panel transition-colors"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={(e) => handleDeleteClick(e, c.id)}
                      className="opacity-0 group-hover:opacity-100 p-1 rounded text-secondary hover:text-rose-600 hover:bg-panel transition-opacity"
                      title="Delete conversation"
                    >
                      <Trash2 className="w-3 h-3" />
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );

  return (
    <>
      {/* Desktop permanent drawer */}
      <div className="hidden md:block h-full">{sidebarContent}</div>

      {/* Mobile drawer with overlay */}
      {isOpen && (
        <div className="fixed inset-0 z-40 flex md:hidden">
          <div
            className="fixed inset-0 bg-black/60 transition-opacity"
            onClick={onClose}
          />
          <div className="relative z-50 flex-1 max-w-xs w-full bg-surface">
            {sidebarContent}
          </div>
        </div>
      )}
    </>
  );
};

export default ConversationSidebar;
