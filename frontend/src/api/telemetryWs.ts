import type {
  AnalyticsUpdateEvent,
  TelemetryEvent,
  WebSocketConnectionStatus,
} from '../types/telemetry';

export type TelemetryHandler = (event: TelemetryEvent) => void;
export type AnalyticsHandler = (event: AnalyticsUpdateEvent) => void;
export type StatusHandler = (status: WebSocketConnectionStatus) => void;

export class TelemetryWebSocketClient {
  private url: string;
  private ws: WebSocket | null = null;
  private status: WebSocketConnectionStatus = 'DISCONNECTED';
  private reconnectAttempts = 0;
  private maxReconnectDelay = 16000;
  private reconnectTimer: number | null = null;
  private isIntentionallyClosed = false;

  private telemetryListeners: Set<TelemetryHandler> = new Set();
  private analyticsListeners: Set<AnalyticsHandler> = new Set();
  private statusListeners: Set<StatusHandler> = new Set();

  constructor(url?: string) {
    const defaultWsUrl =
      import.meta.env.VITE_WS_BASE_URL ??
      `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.hostname || '127.0.0.1'}:8000/ws/telemetry`;
    this.url = url || defaultWsUrl;
  }

  public connect(): void {
    if (
      this.ws &&
      (this.ws.readyState === WebSocket.CONNECTING || this.ws.readyState === WebSocket.OPEN)
    ) {
      return;
    }

    this.isIntentionallyClosed = false;
    this.clearReconnectTimer();
    this.setStatus(this.reconnectAttempts > 0 ? 'RECONNECTING' : 'CONNECTING');

    try {
      this.ws = new WebSocket(this.url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.setStatus('CONNECTED');
      };

      this.ws.onmessage = (event: MessageEvent) => {
        try {
          const parsed = JSON.parse(event.data);
          if (parsed && typeof parsed === 'object') {
            if (parsed.type === 'telemetry') {
              this.telemetryListeners.forEach((fn) => fn(parsed as TelemetryEvent));
            } else if (parsed.type === 'analytics_update') {
              this.analyticsListeners.forEach((fn) => fn(parsed as AnalyticsUpdateEvent));
            }
          }
        } catch (err) {
          console.error('Failed to parse WebSocket telemetry payload:', err);
        }
      };

      this.ws.onerror = () => {
        if (!this.isIntentionallyClosed) {
          this.setStatus('ERROR');
        }
      };

      this.ws.onclose = () => {
        this.ws = null;
        if (!this.isIntentionallyClosed) {
          this.scheduleReconnect();
        } else {
          this.setStatus('DISCONNECTED');
        }
      };
    } catch (err) {
      console.error('Failed to initialize WebSocket client:', err);
      this.setStatus('ERROR');
      this.scheduleReconnect();
    }
  }

  public disconnect(): void {
    this.isIntentionallyClosed = true;
    this.clearReconnectTimer();
    if (this.ws) {
      this.ws.close();
      this.ws = null;
    }
    this.setStatus('DISCONNECTED');
  }

  public onTelemetry(handler: TelemetryHandler): () => void {
    this.telemetryListeners.add(handler);
    return () => {
      this.telemetryListeners.delete(handler);
    };
  }

  public onAnalytics(handler: AnalyticsHandler): () => void {
    this.analyticsListeners.add(handler);
    return () => {
      this.analyticsListeners.delete(handler);
    };
  }

  public onStatusChange(handler: StatusHandler): () => void {
    this.statusListeners.add(handler);
    handler(this.status);
    return () => {
      this.statusListeners.delete(handler);
    };
  }

  public getStatus(): WebSocketConnectionStatus {
    return this.status;
  }

  private setStatus(newStatus: WebSocketConnectionStatus): void {
    if (this.status !== newStatus) {
      this.status = newStatus;
      this.statusListeners.forEach((fn) => fn(newStatus));
    }
  }

  private scheduleReconnect(): void {
    if (this.isIntentionallyClosed) return;
    this.clearReconnectTimer();
    this.setStatus('RECONNECTING');

    const baseDelay = Math.min(1000 * Math.pow(2, this.reconnectAttempts), this.maxReconnectDelay);
    const jitter = Math.random() * 500;
    const delay = baseDelay + jitter;

    this.reconnectAttempts++;

    this.reconnectTimer = window.setTimeout(() => {
      if (!this.isIntentionallyClosed) {
        this.connect();
      }
    }, delay);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }
}

export const telemetryWsClient = new TelemetryWebSocketClient();
