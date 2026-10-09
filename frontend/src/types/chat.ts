export interface CitationItem {
  citation_id: string;
  document_id: string;
  document_filename: string;
  chunk_id: string;
  chunk_index: number;
  page_number: number | null;
  similarity_score: number;
  cosine_distance: number;
  metadata?: Record<string, any>;
}

export interface RAGSourceItem {
  citation_id: string;
  chunk_id: string;
  document_id: string;
  chunk_index: number;
  document_filename: string;
  page_number: number | null;
  similarity_score: number;
  cosine_distance: number;
  metadata?: Record<string, any>;
}

export interface RAGQueryRequest {
  query: string;
  top_k?: number;
  document_id?: string | null;
  min_similarity?: number | null;
  conversation_id?: string | null;
}

export interface RAGQueryResponse {
  query: string;
  answer: string;
  retrieval_count: number;
  sources: RAGSourceItem[];
  citations: CitationItem[];
  insufficient_evidence?: boolean;
  conversation_id?: string | null;
  user_message_id?: string | null;
  assistant_message_id?: string | null;
}

export interface MessageResponse {
  id: string;
  conversation_id: string;
  role: "user" | "assistant" | "system";
  content: string;
  metadata: {
    retrieval_count?: number;
    sources?: RAGSourceItem[];
    citations?: CitationItem[];
    insufficient_evidence?: boolean;
    [key: string]: any;
  };
  created_at: string;
}

export interface ConversationResponse {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  message_count?: number | null;
}

export interface ConversationDetailResponse {
  id: string;
  user_id: string;
  title: string;
  created_at: string;
  updated_at: string;
  messages: MessageResponse[];
}

export interface ConversationListResponse {
  items: ConversationResponse[];
  total: number;
}
