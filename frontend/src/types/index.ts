/** Type definitions for the application. */

export interface User {
  id: number;
  email: string;
  username: string;
  created_at: string;
}

export interface Document {
  id: number;
  title: string;
  content: string;
  owner_id: number;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface DocumentVersion {
  id: number;
  document_id: number;
  creator_id: number;
  version_number: number;
  content: string;
  change_summary?: string;
  created_at: string;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
}

export interface PresenceUser {
  user_id: number;
  username: string;
  is_typing: boolean;
  last_seen: number;
  color?: string;
}

export interface CursorPosition {
  user_id: number;
  username: string;
  position: number;
  selection_start?: number;
  selection_end?: number;
  color?: string;
}

export type OperationType = 'insert' | 'delete' | 'update';

export interface TextOperation {
  type: OperationType;
  position: number;
  text?: string;
  length?: number;
  timestamp: string;
  user_id: number;
  vector_clock: Record<string, number>;
}

export interface WebSocketMessage {
  type: 'operation' | 'cursor' | 'presence' | 'sync' | 'error';
  data: Record<string, unknown>;
  document_id: number;
  user_id: number;
  timestamp: string;
}

export interface EditorState {
  content: string;
  version: number;
  activeUsers: PresenceUser[];
  cursors: Map<number, CursorPosition>;
  isTyping: boolean;
}

export interface ThemeContextType {
  isDark: boolean;
  toggleTheme: () => void;
}
