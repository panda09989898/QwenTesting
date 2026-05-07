/** Zustand store for application state. */
import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { User, Document, PresenceUser, EditorState } from '../types';

interface AuthStore {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
  logout: () => void;
}

interface DocumentStore {
  documents: Document[];
  currentDocument: Document | null;
  isLoading: boolean;
  error: string | null;
  setDocuments: (docs: Document[]) => void;
  setCurrentDocument: (doc: Document | null) => void;
  addDocument: (doc: Document) => void;
  updateDocument: (id: number, updates: Partial<Document>) => void;
  removeDocument: (id: number) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

interface EditorStore extends EditorState {
  setContent: (content: string) => void;
  setVersion: (version: number) => void;
  setActiveUsers: (users: PresenceUser[]) => void;
  addActiveUser: (user: PresenceUser) => void;
  removeActiveUser: (userId: number) => void;
  updateUserTyping: (userId: number, isTyping: boolean) => void;
  setIsTyping: (isTyping: boolean) => void;
  resetEditor: () => void;
}

interface ThemeStore {
  isDark: boolean;
  toggleTheme: () => void;
  setTheme: (isDark: boolean) => void;
}

// Auth Store
export const useAuthStore = create<AuthStore>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      setUser: (user) => set({ user, isAuthenticated: !!user }),
      setToken: (token) => set({ token }),
      logout: () => set({ user: null, token: null, isAuthenticated: false }),
    }),
    { name: 'auth-storage' }
  )
);

// Document Store
export const useDocumentStore = create<DocumentStore>((set) => ({
  documents: [],
  currentDocument: null,
  isLoading: false,
  error: null,
  setDocuments: (docs) => set({ documents: docs }),
  setCurrentDocument: (doc) => set({ currentDocument: doc }),
  addDocument: (doc) =>
    set((state) => ({ documents: [...state.documents, doc] })),
  updateDocument: (id, updates) =>
    set((state) => ({
      documents: state.documents.map((d) =>
        d.id === id ? { ...d, ...updates } : d
      ),
      currentDocument:
        state.currentDocument?.id === id
          ? { ...state.currentDocument, ...updates }
          : state.currentDocument,
    })),
  removeDocument: (id) =>
    set((state) => ({
      documents: state.documents.filter((d) => d.id !== id),
      currentDocument:
        state.currentDocument?.id === id ? null : state.currentDocument,
    })),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
}));

// Editor Store
const generateColor = (userId: number): string => {
  const colors = [
    '#3B82F6', '#EF4444', '#10B981', '#F59E0B', 
    '#8B5CF6', '#EC4899', '#06B6D4', '#84CC16'
  ];
  return colors[userId % colors.length];
};

export const useEditorStore = create<EditorStore>((set) => ({
  content: '',
  version: 0,
  activeUsers: [],
  cursors: new Map(),
  isTyping: false,
  setContent: (content) => set({ content }),
  setVersion: (version) => set({ version }),
  setActiveUsers: (users) => set({ activeUsers: users }),
  addActiveUser: (user) =>
    set((state) => {
      const exists = state.activeUsers.find((u) => u.user_id === user.user_id);
      if (exists) return state;
      return { activeUsers: [...state.activeUsers, { ...user, color: generateColor(user.user_id) }] };
    }),
  removeActiveUser: (userId) =>
    set((state) => ({
      activeUsers: state.activeUsers.filter((u) => u.user_id !== userId),
    })),
  updateUserTyping: (userId, isTyping) =>
    set((state) => ({
      activeUsers: state.activeUsers.map((u) =>
        u.user_id === userId ? { ...u, is_typing: isTyping } : u
      ),
    })),
  setIsTyping: (isTyping) => set({ isTyping }),
  resetEditor: () =>
    set({
      content: '',
      version: 0,
      activeUsers: [],
      cursors: new Map(),
      isTyping: false,
    }),
}));

// Theme Store
export const useThemeStore = create<ThemeStore>()(
  persist(
    (set) => ({
      isDark: false,
      toggleTheme: () => set((state) => ({ isDark: !state.isDark })),
      setTheme: (isDark) => set({ isDark }),
    }),
    { name: 'theme-storage' }
  )
);
