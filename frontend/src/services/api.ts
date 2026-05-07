/** API service for communicating with the backend. */
import axios, { AxiosInstance } from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

class ApiService {
  private client: AxiosInstance;

  constructor() {
    this.client = axios.create({
      baseURL: API_BASE_URL,
      headers: {
        'Content-Type': 'application/json',
      },
    });

    // Request interceptor to add auth token
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem('token');
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    // Response interceptor for error handling
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        if (error.response?.status === 401) {
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          window.location.href = '/login';
        }
        return Promise.reject(error);
      }
    );
  }

  setToken(token: string | null) {
    if (token) {
      localStorage.setItem('token', token);
    } else {
      localStorage.removeItem('token');
    }
  }

  getToken(): string | null {
    return localStorage.getItem('token');
  }

  // Auth endpoints
  async register(email: string, username: string, password: string) {
    const response = await this.client.post('/auth/register', {
      email,
      username,
      password,
    });
    return response.data;
  }

  async login(email: string, password: string) {
    const response = await this.client.post('/auth/login', {
      email,
      password,
    });
    if (response.data.access_token) {
      this.setToken(response.data.access_token);
    }
    return response.data;
  }

  logout() {
    this.setToken(null);
    localStorage.removeItem('user');
  }

  async getCurrentUser() {
    const response = await this.client.get('/auth/me');
    return response.data;
  }

  // Document endpoints
  async getDocuments(page = 0, pageSize = 20) {
    const response = await this.client.get('/documents', {
      params: { page, page_size: pageSize },
    });
    return response.data;
  }

  async getDocument(id: number) {
    const response = await this.client.get(`/documents/${id}`);
    return response.data;
  }

  async createDocument(title: string, content = '') {
    const response = await this.client.post('/documents', {
      title,
      content,
    });
    return response.data;
  }

  async updateDocument(id: number, updates: { title?: string; content?: string }) {
    const response = await this.client.put(`/documents/${id}`, updates);
    return response.data;
  }

  async deleteDocument(id: number) {
    await this.client.delete(`/documents/${id}`);
  }

  async getVersionHistory(documentId: number, page = 0, pageSize = 20) {
    const response = await this.client.get(`/documents/${documentId}/versions`, {
      params: { page, page_size: pageSize },
    });
    return response.data;
  }

  async restoreVersion(documentId: number, versionId: number) {
    const response = await this.client.post(
      `/documents/${documentId}/versions/${versionId}/restore`
    );
    return response.data;
  }
}

export const apiService = new ApiService();
export default apiService;
