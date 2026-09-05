/**
 * WebSocket клиент для SpectechPlatform.
 *
 * Использование:
 *   const ws = new SpectechWebSocket(token, {
 *     onGpsPoint: (point) => console.log(point),
 *     onAlert: (alert) => console.log(alert),
 *   });
 */

type MessageHandler = (data: any) => void;

interface WebSocketHandlers {
  onConnected?: (data: any) => void;
  onGpsPoint?: (data: any) => void;
  onAlert?: (data: any) => void;
  onRequestStatus?: (data: any) => void;
  onPong?: (data: any) => void;
  onStats?: (data: any) => void;
  onError?: (error: string) => void;
  onDisconnected?: () => void;
}

export class SpectechWebSocket {
  private ws: WebSocket | null = null;
  private token: string;
  private handlers: WebSocketHandlers;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000; // 1 second
  private pingInterval: NodeJS.Timeout | null = null;
  private isManualClose = false;

  constructor(token: string, handlers: WebSocketHandlers = {}) {
    this.token = token;
    this.handlers = handlers;
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      console.log("WebSocket already connected");
      return;
    }

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = process.env.NEXT_PUBLIC_WS_HOST || "localhost:8000";
    const url = `${protocol}//${host}/api/v1/ws?token=${this.token}`;

    console.log("Connecting to WebSocket:", url);

    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      console.log("✅ WebSocket connected");
      this.reconnectAttempts = 0;
      this.startPing();
    };

    this.ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        this.handleMessage(data);
      } catch (e) {
        console.error("Failed to parse WebSocket message:", e);
      }
    };

    this.ws.onerror = (error) => {
      console.error("❌ WebSocket error:", error);
      this.handlers.onError?.("WebSocket error");
    };

    this.ws.onclose = (event) => {
      console.log(`WebSocket closed: code=${event.code}, reason=${event.reason}`);
      this.stopPing();
      this.handlers.onDisconnected?.();

      // Авто-переподключение
      if (!this.isManualClose && this.reconnectAttempts < this.maxReconnectAttempts) {
        const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts);
        console.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts + 1})`);
        setTimeout(() => {
          this.reconnectAttempts++;
          this.connect();
        }, delay);
      }
    };
  }

  private handleMessage(data: any): void {
    switch (data.type) {
      case "connected":
        this.handlers.onConnected?.(data);
        break;
      case "pong":
        this.handlers.onPong?.(data);
        break;
      case "gps_point":
        this.handlers.onGpsPoint?.(data);
        break;
      case "alert":
        this.handlers.onAlert?.(data);
        break;
      case "request_status":
        this.handlers.onRequestStatus?.(data);
        break;
      case "stats":
        this.handlers.onStats?.(data);
        break;
      case "error":
        console.error("Server error:", data.message);
        this.handlers.onError?.(data.message);
        break;
      default:
        console.log("Unknown message type:", data);
    }
  }

  private startPing(): void {
    // Отправляем ping каждые 30 секунд для поддержания соединения
    this.pingInterval = setInterval(() => {
      this.send({ type: "ping" });
    }, 30000);
  }

  private stopPing(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  send(data: any): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    } else {
      console.warn("WebSocket not connected, cannot send:", data);
    }
  }

  subscribe(channel: "gps" | "alerts" | "requests" | "all"): void {
    this.send({ type: "subscribe", channel });
  }

  unsubscribe(channel: string): void {
    this.send({ type: "unsubscribe", channel });
  }

  requestStats(): void {
    this.send({ type: "stats" });
  }

  disconnect(): void {
    this.isManualClose = true;
    this.stopPing();
    if (this.ws) {
      this.ws.close(1000, "Manual disconnect");
      this.ws = null;
    }
  }

  isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}
