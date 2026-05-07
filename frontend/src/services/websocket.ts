/** WebSocket service for real-time collaboration. */
import { PresenceUser, TextOperation, CursorPosition } from '../types';

const WS_BASE_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000';

type MessageHandler = (data: unknown) => void;

interface WSMessage {
  type: string;
  data: Record<string, unknown>;
}

class WebSocketService {
  private ws: WebSocket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private messageHandlers: Map<string, Set<MessageHandler>> = new Map();
  private documentId: number | null = null;
  private pingInterval: number | null = null;

  connect(documentId: number, token: string): Promise<void> {
    return new Promise((resolve, reject) => {
      this.documentId = documentId;
      const wsUrl = `${WS_BASE_URL}/documents/ws/${documentId}?token=${token}`;
      
      try {
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
          console.log('WebSocket connected');
          this.reconnectAttempts = 0;
          this.startPingInterval();
          resolve();
        };

        this.ws.onmessage = (event) => {
          try {
            const message: WSMessage = JSON.parse(event.data);
            this.handleMessage(message);
          } catch (error) {
            console.error('Error parsing WebSocket message:', error);
          }
        };

        this.ws.onclose = (event) => {
          console.log('WebSocket closed:', event.code, event.reason);
          this.stopPingInterval();
          this.attemptReconnect(documentId, token);
        };

        this.ws.onerror = (error) => {
          console.error('WebSocket error:', error);
          reject(error);
        };
      } catch (error) {
        reject(error);
      }
    });
  }

  disconnect() {
    this.stopPingInterval();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.documentId = null;
  }

  private startPingInterval() {
    this.pingInterval = window.setInterval(() => {
      this.send({ type: 'presence', data: { is_typing: false } });
    }, 30000);
  }

  private stopPingInterval() {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private attemptReconnect(documentId: number, token: string) {
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnection attempts reached');
      this.emit('disconnected', { reason: 'max_attempts' });
      return;
    }

    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
    
    console.log(`Attempting to reconnect in ${delay}ms (attempt ${this.reconnectAttempts})`);
    
    setTimeout(() => {
      this.connect(documentId, token).catch(console.error);
    }, delay);
  }

  private handleMessage(message: WSMessage) {
    const handlers = this.messageHandlers.get(message.type);
    if (handlers) {
      handlers.forEach((handler) => handler(message.data));
    }
    
    // Also emit generic message event
    this.emit('message', message);
  }

  on(eventType: string, handler: MessageHandler) {
    if (!this.messageHandlers.has(eventType)) {
      this.messageHandlers.set(eventType, new Set());
    }
    this.messageHandlers.get(eventType)!.add(handler);
    
    // Return unsubscribe function
    return () => {
      this.messageHandlers.get(eventType)?.delete(handler);
    };
  }

  off(eventType: string, handler: MessageHandler) {
    this.messageHandlers.get(eventType)?.delete(handler);
  }

  private emit(eventType: string, data: unknown) {
    const handlers = this.messageHandlers.get(eventType);
    if (handlers) {
      handlers.forEach((handler) => handler(data));
    }
  }

  send(message: WSMessage) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket not connected, message not sent:', message);
    }
  }

  // Operation methods
  sendOperation(operation: TextOperation) {
    this.send({
      type: 'operation',
      data: operation,
    });
  }

  sendCursor(cursor: CursorPosition) {
    this.send({
      type: 'cursor',
      data: cursor,
    });
  }

  sendPresence(isTyping: boolean) {
    this.send({
      type: 'presence',
      data: { is_typing: isTyping },
    });
  }

  requestSync(baseVersion: number) {
    this.send({
      type: 'sync',
      data: { base_version: baseVersion },
    });
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

export const wsService = new WebSocketService();
export default wsService;
