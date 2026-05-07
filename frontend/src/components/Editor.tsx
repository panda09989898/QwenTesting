/** Collaborative document editor component. */
import { useState, useEffect, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useEditorStore, useDocumentStore, useAuthStore } from '../store';
import { useWebSocket } from '../hooks';
import apiService from '../services/api';

export default function Editor() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const documentId = id ? parseInt(id) : null;
  
  const { token, user } = useAuthStore();
  const { currentDocument, setCurrentDocument, updateDocument, setLoading } = useDocumentStore();
  const { content, setContent, version, activeUsers, isTyping, setVersion, setActiveUsers } = useEditorStore();
  
  const [title, setTitle] = useState('');
  const [isSaving, setIsSaving] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  
  // Connect to WebSocket
  const { isConnected, sendTypingIndicator } = useWebSocket(documentId);
  
  // Load document on mount
  useEffect(() => {
    if (!documentId) return;
    
    const loadDocument = async () => {
      setLoading(true);
      try {
        const doc = await apiService.getDocument(documentId);
        setCurrentDocument(doc);
        setTitle(doc.title);
        setContent(doc.content);
        setVersion(doc.version);
      } catch (error) {
        console.error('Failed to load document:', error);
      } finally {
        setLoading(false);
      }
    };
    
    loadDocument();
  }, [documentId]);
  
  // Handle text changes with optimistic updates
  const handleTextChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const newContent = e.target.value;
    setContent(newContent);
    
    // Send operation via WebSocket
    if (isConnected) {
      sendTypingIndicator(true);
      
      // In a real implementation, we'd compute the diff and send operations
      // For simplicity, we're sending the full content change
      // TODO: Implement proper OT/CRDT for production
    }
  };
  
  // Debounced save
  useEffect(() => {
    const timer = setTimeout(async () => {
      if (!documentId || !content) return;
      
      setIsSaving(true);
      try {
        await apiService.updateDocument(documentId, { content });
        updateDocument(documentId, { content, version: version + 1 });
      } catch (error) {
        console.error('Failed to save document:', error);
      } finally {
        setIsSaving(false);
      }
    }, 1000);
    
    return () => clearTimeout(timer);
  }, [content, documentId]);
  
  // Handle title change
  const handleTitleBlur = async () => {
    if (!documentId || title === currentDocument?.title) return;
    
    try {
      await apiService.updateDocument(documentId, { title });
      updateDocument(documentId, { title });
    } catch (error) {
      console.error('Failed to update title:', error);
    }
  };
  
  if (!documentId) {
    return <div className="p-4">Document not found</div>;
  }
  
  return (
    <div className="max-w-5xl mx-auto px-4">
      {/* Header */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex-1">
          <input
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onBlur={handleTitleBlur}
            className="text-2xl font-bold bg-transparent border-none focus:outline-none focus:ring-2 focus:ring-primary-500 rounded px-2 py-1 dark:text-white w-full"
            placeholder="Untitled Document"
          />
        </div>
        <div className="flex items-center gap-4">
          <span className={`text-sm ${isConnected ? 'text-green-600' : 'text-red-600'}`}>
            {isConnected ? '● Connected' : '○ Disconnected'}
          </span>
          {isSaving && <span className="text-sm text-gray-500">Saving...</span>}
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="px-3 py-1 text-sm border dark:border-dark-border rounded hover:bg-gray-100 dark:hover:bg-dark-surface"
          >
            History
          </button>
          <button
            onClick={() => navigate('/')}
            className="px-3 py-1 text-sm bg-gray-200 dark:bg-dark-surface rounded hover:bg-gray-300"
          >
            Back
          </button>
        </div>
      </div>
      
      {/* Active users / presence indicators */}
      {activeUsers.length > 0 && (
        <div className="mb-4 flex items-center gap-2 flex-wrap">
          <span className="text-sm text-gray-500">Active:</span>
          {activeUsers.map((u) => (
            <div
              key={u.user_id}
              className="flex items-center gap-1 px-2 py-1 rounded-full text-xs text-white"
              style={{ backgroundColor: u.color || '#3B82F6' }}
            >
              <span>{u.username}</span>
              {u.is_typing && <span className="typing-indicator">·</span>}
            </div>
          ))}
        </div>
      )}
      
      {/* Editor */}
      <div className="bg-white dark:bg-dark-surface rounded-lg shadow-sm border dark:border-dark-border overflow-hidden">
        <textarea
          ref={textareaRef}
          value={content}
          onChange={handleTextChange}
          className="w-full h-[60vh] p-6 resize-none focus:outline-none dark:bg-dark-surface dark:text-white font-mono text-sm leading-relaxed"
          placeholder="Start writing..."
          spellCheck={false}
        />
      </div>
      
      {/* Version info */}
      <div className="mt-4 text-sm text-gray-500">
        Version {version} • Last updated just now
      </div>
      
      {/* Version history panel */}
      {showHistory && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white dark:bg-dark-surface rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4 dark:text-white">Version History</h3>
            <p className="text-sm text-gray-500 mb-4">Version history feature coming soon...</p>
            <button
              onClick={() => setShowHistory(false)}
              className="w-full py-2 bg-primary-600 text-white rounded hover:bg-primary-700"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
