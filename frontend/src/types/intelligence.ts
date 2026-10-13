export interface DocumentSummaryRequest {
  mode: "concise" | "detailed";
  force_refresh?: boolean;
}

export interface DocumentSummaryResponse {
  document_id: string;
  document_filename: string;
  mode: string;
  summary: string;
  key_takeaways: string[];
  cached: boolean;
  generated_at?: string;
}

export interface DocumentComparisonRequest {
  document_ids: string[];
  comparison_prompt?: string;
}

export interface DocumentComparisonSource {
  document_id: string;
  filename: string;
  page_number: number | null;
  excerpt: string;
}

export interface DocumentComparisonItem {
  id: string;
  filename: string;
}

export interface DocumentComparisonResponse {
  comparison_id: string;
  documents: DocumentComparisonItem[];
  focus_prompt: string;
  synthesis: string;
  sources: DocumentComparisonSource[];
}

export interface StructuredExtractionRequest {
  target_fields?: string[];
}

export interface StructuredExtractionResponse {
  document_id: string;
  document_filename: string;
  data: Record<string, any>;
}

export interface ReportGenerateRequest {
  topic: string;
  title?: string;
  document_ids?: string[];
  collection_id?: string;
}

export interface ReportGenerateResponse {
  report_id: string;
  title: string;
  topic: string;
  generated_at: string;
  content_markdown: string;
  documents_count: number;
  sources: Array<{
    document_id: string;
    filename: string;
    page_number: number | null;
    excerpt: string;
  }>;
}

export interface DeepResearchStep {
  subquestion: string;
  findings: string;
  sources_count: number;
}

export interface DeepResearchRequest {
  topic: string;
  document_id?: string;
  max_subquestions?: number;
}

export interface DeepResearchResponse {
  research_id: string;
  topic: string;
  subquestions: string[];
  steps: DeepResearchStep[];
  synthesis: string;
  sources: Array<{
    document_id: string;
    filename: string;
    page_number: number | null;
    excerpt: string;
  }>;
  has_conflicts: boolean;
}

export interface KnowledgeGraphNode {
  id: string;
  name: string;
  type: string;
}

export interface KnowledgeGraphLink {
  source: string;
  target: string;
  relationship: string;
  source_doc?: string;
}

export interface KnowledgeGraphResponse {
  nodes: KnowledgeGraphNode[];
  links: KnowledgeGraphLink[];
  total_entities: number;
  total_relationships: number;
}
