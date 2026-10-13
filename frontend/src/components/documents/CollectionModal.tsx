import React, { useState, useEffect } from "react";
import { X, Folder, Plus, Trash2, FolderPlus, CheckCircle2, Layers } from "lucide-react";
import Button from "../common/Button";
import Input from "../common/Input";
import { CollectionItem } from "../../types/collection";
import { collectionService } from "../../services/collectionService";

interface CollectionModalProps {
  onClose: () => void;
  onCollectionsUpdated?: () => void;
  assignDocumentId?: string; // If set, allow directly assigning this document
}

export const CollectionModal: React.FC<CollectionModalProps> = ({
  onClose,
  onCollectionsUpdated,
  assignDocumentId,
}) => {
  const [collections, setCollections] = useState<CollectionItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // New collection form state
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [isCreating, setIsCreating] = useState(false);

  useEffect(() => {
    loadCollections();
  }, []);

  const loadCollections = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await collectionService.getCollections();
      setCollections(res.items);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to load collections.");
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!name.trim()) return;
    setIsCreating(true);
    setError(null);
    try {
      await collectionService.createCollection({
        name: name.trim(),
        description: description.trim() || undefined,
      });
      setName("");
      setDescription("");
      setSuccess("Collection created successfully.");
      await loadCollections();
      if (onCollectionsUpdated) onCollectionsUpdated();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to create collection.");
    } finally {
      setIsCreating(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await collectionService.deleteCollection(id);
      await loadCollections();
      if (onCollectionsUpdated) onCollectionsUpdated();
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to delete collection.");
    }
  };

  const handleAssign = async (collectionId: string) => {
    if (!assignDocumentId) return;
    try {
      await collectionService.addDocument(collectionId, assignDocumentId);
      setSuccess("Document assigned to collection.");
      await loadCollections();
      if (onCollectionsUpdated) onCollectionsUpdated();
      setTimeout(() => setSuccess(null), 3000);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to assign document.");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div className="bg-surface border border-border rounded-lg shadow-xl w-full max-w-lg max-h-[85vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="p-4 border-b border-border flex items-center justify-between bg-panel/40">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded bg-accent/15 border border-accent/25 flex items-center justify-center text-accent">
              <Folder className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-primary">Document Collections</h3>
              <p className="text-xs text-secondary">
                {assignDocumentId
                  ? "Assign asset to a curated knowledge collection"
                  : "Organize documents into isolated domain workspaces"}
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded text-secondary hover:text-primary hover:bg-canvas transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Status Alerts */}
        {error && (
          <div className="mx-4 mt-3 p-2.5 rounded bg-red-500/10 border border-red-500/20 text-xs text-red-600 dark:text-red-400">
            {error}
          </div>
        )}
        {success && (
          <div className="mx-4 mt-3 p-2.5 rounded bg-emerald-500/10 border border-emerald-500/20 text-xs text-emerald-600 dark:text-emerald-400 flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5" />
            {success}
          </div>
        )}

        {/* Create Collection Form */}
        <form onSubmit={handleCreate} className="p-4 border-b border-border bg-panel/20 space-y-2.5">
          <div className="text-xs font-semibold text-primary">New Collection</div>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="Collection name (e.g., Financial Filings, Legal NDAs)..."
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="flex-1 text-xs px-3 py-1.5 rounded bg-surface border border-border text-primary placeholder:text-secondary/60 focus:outline-none focus:ring-1 focus:ring-accent"
            />
            <Button
              type="submit"
              variant="primary"
              size="sm"
              disabled={isCreating || !name.trim()}
              className="text-xs shrink-0 flex items-center gap-1"
            >
              <Plus className="w-3.5 h-3.5" />
              Create
            </Button>
          </div>
        </form>

        {/* Existing Collections List */}
        <div className="p-4 overflow-y-auto space-y-2 flex-1">
          <div className="text-[11px] font-semibold text-secondary uppercase tracking-wider mb-2">
            Active Collections ({collections.length})
          </div>

          {loading ? (
            <div className="py-8 text-center text-xs text-secondary">Loading collections...</div>
          ) : collections.length === 0 ? (
            <div className="py-8 text-center text-xs text-secondary">
              No collections found. Create your first collection above.
            </div>
          ) : (
            collections.map((col) => (
              <div
                key={col.id}
                className="p-3 rounded-lg border border-border bg-panel/30 hover:bg-panel/50 transition-colors flex items-center justify-between gap-3 text-xs"
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <Folder className="w-4 h-4 text-accent shrink-0" />
                    <span className="font-semibold text-primary truncate">{col.name}</span>
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-panel border border-border/60 text-secondary">
                      {col.documents_count} {col.documents_count === 1 ? "doc" : "docs"}
                    </span>
                  </div>
                  {col.description && (
                    <p className="text-[11px] text-secondary mt-0.5 truncate pl-6">
                      {col.description}
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  {assignDocumentId && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleAssign(col.id)}
                      className="h-7 text-xs"
                    >
                      Assign
                    </Button>
                  )}
                  <button
                    onClick={() => handleDelete(col.id)}
                    className="p-1 rounded text-secondary hover:text-red-500 transition-colors"
                    title="Delete collection"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer */}
        <div className="p-3 border-t border-border bg-panel/40 flex justify-end">
          <Button variant="secondary" size="sm" onClick={onClose} className="text-xs">
            Close
          </Button>
        </div>
      </div>
    </div>
  );
};

export default CollectionModal;
