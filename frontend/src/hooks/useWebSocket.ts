import { useEffect, useRef, useCallback } from "react";
import type { WsMessage } from "../types";

export function useWebSocket(
  url: string,
  onMessages: (msgs: WsMessage[]) => void
) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const batch: WsMessage[] = JSON.parse(event.data);
        onMessages(batch);
      } catch {
        // ignore malformed
      }
    };

    ws.onclose = () => {
      reconnectTimer.current = setTimeout(connect, 2000);
    };

    ws.onerror = () => ws.close();
  }, [url, onMessages]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);
}
