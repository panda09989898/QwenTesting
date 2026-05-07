/** Dashboard component showing document list. */
import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useDocumentStore } from '../store';
import apiService from '../services/api';
import { formatRelativeTime, truncate } from '../utils';

export default function Dashboard() {
  const { documents, setDocuments, setLoading, isLoading } = useDocumentStore();
  const [newDocTitle, setNewDocTitle] = useState('');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    loadDocuments();
  }, []);

  const loadDocuments = async () => {
    setLoading(true);
    try {
      const data = await apiService.getDocuments();
      setDocuments(data.documents || []);
    } catch (error) {
      console.error('Failed to load documents:', error);
    } finally {
      setLoading(false);
    }
  };

  const createDocument = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newDocTitle.trim()) return;

    setCreating(true);
    try {
      const doc = await apiService.createDocument(newDocTitle);
      setDocuments([doc, ...documents]);
      setNewDocTitle('');
    } catch (error) {
      console.error('Failed to create document:', error);
    } finally {
      setCreating(false);
    }
  };

  const deleteDocument = async (id: number) => {
    if (!confirm('Are you sure you want to delete this document?')) return;
    
    try {
      await apiService.deleteDocument(id);
      setDocuments(documents.filter((d) => d.id !== id));
    } catch (error) {
      console.error('Failed to delete document:', error);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600"></div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">My Documents</h1>
      </div>

      <form onSubmit={createDocument} className="mb-8 flex gap-4">
        <input
          type="text"
          value={newDocTitle}
          onChange={(e) => setNewDocTitle(e.target.value)}
          placeholder="New document title..."
          className="flex-1 px-4 py-2 border border-gray-300 dark:border-dark-border rounded-md dark:bg-dark-surface dark:text-white"
        />
        <button
          type="submit"
          disabled={creating || !newDocTitle.trim()}
          className="px-6 py-2 bg-primary-600 text-white rounded-md hover:bg-primary-700 disabled:opacity-50"
        >
          Create
        </button>
      </form>

      {documents.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500 dark:text-gray-400">No documents yet. Create your first one!</p>
        </div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {documents.map((doc) => (
            <div
              key={doc.id}
              className="bg-white dark:bg-dark-surface rounded-lg shadow-sm border dark:border-dark-border p-4 hover:shadow-md transition-shadow"
            >
              <Link to={`/document/${doc.id}`} className="block">
                <h3 className="font-semibold text-gray-900 dark:text-white mb-2">
                  {truncate(doc.title, 30)}
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
                  {truncate(doc.content || 'Empty document', 80)}
                </p>
                <div className="flex justify-between items-center text-xs text-gray-400">
                  <span>v{doc.version}</span>
                  <span>{formatRelativeTime(doc.updated_at)}</span>
                </div>
              </Link>
              <button
                onClick={(e) => {
                  e.preventDefault();
                  deleteDocument(doc.id);
                }}
                className="mt-3 text-xs text-red-600 hover:text-red-700"
              >
                Delete
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
