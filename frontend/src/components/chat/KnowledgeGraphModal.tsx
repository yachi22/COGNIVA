import React, { useState, useEffect } from "react";
import { X, Network, RefreshCw, ZoomIn, ZoomOut, Filter, Info } from "lucide-react";
import Button from "../common/Button";
import Badge from "../common/Badge";
import { KnowledgeGraphResponse, KnowledgeGraphNode, KnowledgeGraphLink } from "../../types/intelligence";
import { researchService } from "../../services/researchService";

interface KnowledgeGraphModalProps {
  onClose: () => void;
  documentId?: string;
}

export const KnowledgeGraphModal: React.FC<KnowledgeGraphModalProps> = ({
  onClose,
  documentId,
}) => {
  const [loading, setLoading] = useState(false);
  const [graphData, setGraphData] = useState<KnowledgeGraphResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<KnowledgeGraphNode | null>(null);
  const [selectedLink, setSelectedLink] = useState<KnowledgeGraphLink | null>(null);

  useEffect(() => {
    loadGraph();
  }, [documentId]);

  const loadGraph = async () => {
    setLoading(true);
    setError(null);
    setSelectedNode(null);
    setSelectedLink(null);
    try {
      const res = await researchService.getKnowledgeGraph(documentId, 10);
      setGraphData(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Failed to load knowledge graph.");
    } finally {
      setLoading(false);
    }
  };

  const getNodeColor = (type: string) => {
    const t = type.toUpperCase();
    if (t.includes("ORG") || t.includes("COMPANY")) return "#267653"; // Forest green / accent
    if (t.includes("PERSON") || t.includes("ACTOR")) return "#3b82f6"; // Blue
    if (t.includes("REG") || t.includes("LEGAL") || t.includes("RULE")) return "#8b5cf6"; // Purple
    if (t.includes("METRIC") || t.includes("DATE") || t.includes("NUM")) return "#f59e0b"; // Amber
    if (t.includes("RISK") || t.includes("OBLIGATION")) return "#ef4444"; // Red
    return "#6b7280"; // Gray
  };

  // Node position helper: arrange nodes in a circular / elliptical layout
  const getNodePosition = (index: number, total: number, width: number, height: number) => {
    if (total === 1) return { x: width / 2, y: height / 2 };
    const radius = Math.min(width, height) * 0.38;
    const angle = (index / total) * 2 * Math.PI - Math.PI / 2;
    return {
      x: width / 2 + radius * Math.cos(angle),
      y: height / 2 + radius * Math.sin(angle),
    };
  };

  const svgWidth = 720;
  const svgHeight = 440;

  const nodePositions = (graphData?.nodes || []).reduce<Record<string, { x: number; y: number }>>(
    (acc, node, idx) => {
      acc[node.id] = getNodePosition(idx, graphData!.nodes.length, svgWidth, svgHeight);
      return acc;
    },
    {}
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-xs">
      <div className="bg-surface border border-border rounded-lg shadow-xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="p-4 border-b border-border flex items-center justify-between bg-panel/40">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded bg-accent/15 border border-accent/25 flex items-center justify-center text-accent">
              <Network className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-semibold text-primary">Enterprise Knowledge Graph</h3>
              <p className="text-xs text-secondary">
                Entity relationships extracted from authorized tenant documentation
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

        {/* Toolbar */}
        <div className="px-4 py-2 bg-canvas/60 border-b border-border flex items-center justify-between flex-wrap gap-2 text-xs">
          <div className="flex items-center gap-3">
            <span className="text-secondary">
              Entities: <strong className="text-primary">{graphData?.total_entities || 0}</strong>
            </span>
            <span>•</span>
            <span className="text-secondary">
              Relationships: <strong className="text-primary">{graphData?.total_relationships || 0}</strong>
            </span>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={loadGraph}
            disabled={loading}
            className="h-7 text-xs flex items-center gap-1.5"
          >
            <RefreshCw className={`w-3 h-3 ${loading ? "animate-spin" : ""}`} />
            Refresh Graph
          </Button>
        </div>

        {/* Interactive Graph Surface */}
        <div className="p-4 flex-1 flex flex-col md:flex-row gap-4 overflow-hidden min-h-[460px]">
          {loading ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center space-y-3">
              <RefreshCw className="w-7 h-7 text-accent animate-spin" />
              <p className="text-xs text-secondary">
                Extracting named entities and relational linkages across corpus...
              </p>
            </div>
          ) : error ? (
            <div className="flex-1 p-4 rounded bg-red-500/10 border border-red-500/20 text-xs text-red-600 dark:text-red-400">
              {error}
            </div>
          ) : !graphData || graphData.nodes.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-8 space-y-2">
              <Network className="w-10 h-10 text-secondary/40" />
              <p className="text-sm font-medium text-primary">No Graph Entities Discovered</p>
              <p className="text-xs text-secondary max-w-sm">
                Upload and process documents in the Knowledge Library to extract entities and relational links automatically.
              </p>
            </div>
          ) : (
            <>
              {/* SVG Canvas */}
              <div className="flex-1 bg-panel/30 border border-border/80 rounded-lg relative overflow-hidden flex items-center justify-center">
                <svg
                  viewBox={`0 0 ${svgWidth} ${svgHeight}`}
                  className="w-full h-full select-none cursor-default"
                >
                  {/* Links / Edges */}
                  <g className="links">
                    {graphData.links.map((link, idx) => {
                      const sourcePos = nodePositions[link.source];
                      const targetPos = nodePositions[link.target];
                      if (!sourcePos || !targetPos) return null;

                      const isSelected = selectedLink === link;
                      const midX = (sourcePos.x + targetPos.x) / 2;
                      const midY = (sourcePos.y + targetPos.y) / 2;

                      return (
                        <g
                          key={idx}
                          className="cursor-pointer"
                          onClick={() => {
                            setSelectedLink(link);
                            setSelectedNode(null);
                          }}
                        >
                          <line
                            x1={sourcePos.x}
                            y1={sourcePos.y}
                            x2={targetPos.x}
                            y2={targetPos.y}
                            stroke={isSelected ? "#42B883" : "currentColor"}
                            className={isSelected ? "stroke-2" : "stroke-1 text-border/90"}
                            strokeDasharray={isSelected ? undefined : "3 2"}
                          />
                          {/* Relationship label */}
                          <text
                            x={midX}
                            y={midY}
                            fill="currentColor"
                            className="text-[9px] text-secondary fill-secondary"
                            textAnchor="middle"
                            dy="-3"
                          >
                            {link.relationship}
                          </text>
                        </g>
                      );
                    })}
                  </g>

                  {/* Nodes */}
                  <g className="nodes">
                    {graphData.nodes.map((node) => {
                      const pos = nodePositions[node.id];
                      if (!pos) return null;
                      const isSelected = selectedNode?.id === node.id;
                      const color = getNodeColor(node.type);

                      return (
                        <g
                          key={node.id}
                          transform={`translate(${pos.x}, ${pos.y})`}
                          className="cursor-pointer transition-transform hover:scale-110"
                          onClick={() => {
                            setSelectedNode(node);
                            setSelectedLink(null);
                          }}
                        >
                          <circle
                            r={isSelected ? 18 : 14}
                            fill={color}
                            stroke={isSelected ? "#ffffff" : "transparent"}
                            strokeWidth="2"
                            className="drop-shadow-xs"
                          />
                          <text
                            y={isSelected ? 28 : 24}
                            textAnchor="middle"
                            className="text-[10px] font-medium fill-primary drop-shadow-xs"
                          >
                            {node.name.length > 18 ? node.name.slice(0, 16) + "..." : node.name}
                          </text>
                        </g>
                      );
                    })}
                  </g>
                </svg>
              </div>

              {/* Inspector Sidebar */}
              <div className="w-full md:w-64 border border-border/80 rounded-lg p-3.5 bg-surface flex flex-col justify-between text-xs">
                <div>
                  <h4 className="font-semibold text-primary mb-2 flex items-center gap-1.5">
                    <Info className="w-3.5 h-3.5 text-accent" />
                    Inspection Details
                  </h4>

                  {selectedNode ? (
                    <div className="space-y-2">
                      <div>
                        <span className="text-[10px] text-secondary uppercase font-semibold">Entity</span>
                        <p className="font-medium text-primary text-sm mt-0.5">{selectedNode.name}</p>
                      </div>
                      <div>
                        <span className="text-[10px] text-secondary uppercase font-semibold">Classification</span>
                        <div className="mt-0.5">
                          <Badge variant="neutral" className="text-[10px]">
                            {selectedNode.type}
                          </Badge>
                        </div>
                      </div>
                    </div>
                  ) : selectedLink ? (
                    <div className="space-y-2">
                      <div>
                        <span className="text-[10px] text-secondary uppercase font-semibold">Relationship</span>
                        <p className="font-medium text-accent text-xs mt-0.5">{selectedLink.relationship}</p>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-[11px]">
                        <div>
                          <span className="text-secondary">Source:</span>
                          <p className="font-medium text-primary">{selectedLink.source}</p>
                        </div>
                        <div>
                          <span className="text-secondary">Target:</span>
                          <p className="font-medium text-primary">{selectedLink.target}</p>
                        </div>
                      </div>
                      {selectedLink.source_doc && (
                        <div>
                          <span className="text-[10px] text-secondary uppercase font-semibold">Provenance</span>
                          <p className="text-[11px] text-secondary truncate mt-0.5">
                            {selectedLink.source_doc}
                          </p>
                        </div>
                      )}
                    </div>
                  ) : (
                    <p className="text-secondary text-[11px]">
                      Click any entity node or connection line to inspect extracted provenance and relational attributes.
                    </p>
                  )}
                </div>

                <div className="pt-3 border-t border-border/60 text-[10px] text-secondary">
                  Nodes color-coded by ontology category: Org (Green), Person (Blue), Regulation (Purple), Metric (Amber).
                </div>
              </div>
            </>
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

export default KnowledgeGraphModal;
