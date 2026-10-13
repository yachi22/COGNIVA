export interface CollectionDocumentItem {
  id: string;
  filename: string;
  original_filename: string;
  file_type: string;
  status: string;
  created_at: string;
}

export interface CollectionItem {
  id: string;
  user_id: string;
  name: string;
  description?: string | null;
  color?: string | null;
  created_at: string;
  updated_at?: string | null;
  documents_count: number;
  documents?: CollectionDocumentItem[];
}

export interface CollectionCreate {
  name: string;
  description?: string;
  color?: string;
}

export interface CollectionUpdate {
  name?: string;
  description?: string;
  color?: string;
}

export interface CollectionListResponse {
  items: CollectionItem[];
  total: number;
}
