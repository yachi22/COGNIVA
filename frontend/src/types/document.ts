export interface DocumentMetadata {
  size_bytes?: number;
  content_type?: string;
  original_filename?: string;
  stored_filename?: string;
  extracted_path?: string;
  extracted_at?: string;
  total_pages?: number | null;
  total_units?: number;
  total_characters?: number;
  total_words?: number;
  error?: string;
  [key: string]: unknown;
}

export type DocumentStatus = "uploaded" | "processing" | "processed" | "failed";

export interface DocumentItem {
  id: string;
  user_id: string;
  filename: string;
  original_filename: string;
  file_type: "pdf" | "docx" | string;
  status: DocumentStatus | string;
  metadata: DocumentMetadata;
  created_at: string;
  updated_at: string;
}

export interface ExtractedUnit {
  unit_type: "page" | "paragraph" | "heading" | "table" | string;
  page_number: number | null;
  sequence_number: number;
  text: string;
  metadata: Record<string, unknown>;
}

export interface ExtractedDocument {
  document_id: string;
  file_type: string;
  total_pages: number | null;
  total_units: number;
  total_characters: number;
  total_words: number;
  units: ExtractedUnit[];
  extracted_at: string;
}

export interface DocumentUploadResponse extends DocumentItem {}

export interface DocumentDeleteResponse {
  message: string;
  id: string;
}

export interface DocumentChunkDetail {
  id: string;
  document_id: string;
  document_filename: string;
  chunk_index: number;
  content: string;
  page_number: number | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface DocumentChunkItem {
  id: string;
  document_id: string;
  chunk_index: number;
  content: string;
  page_number: number | null;
  metadata_?: Record<string, unknown>;
  created_at: string;
}

export interface DocumentChunkListResponse {
  total: number;
  document_id: string;
  chunks: DocumentChunkItem[];
}

export type JobStatus = "pending" | "processing" | "completed" | "failed" | "cancelled";
export type JobStage = "queued" | "extracting" | "chunking" | "embedding" | "indexing" | "completed" | "failed";

export interface DocumentJob {
  id: string;
  document_id: string;
  user_id: string;
  status: JobStatus | string;
  stage: JobStage | string;
  progress: number;
  current_stage: number;
  total_stages: number;
  retry_count: number;
  max_retries: number;
  error_message?: string | null;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  started_at?: string | null;
  completed_at?: string | null;
}

export interface DocumentJobListResponse {
  total: number;
  document_id: string;
  jobs: DocumentJob[];
}

