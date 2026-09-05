"use client";

import { useEffect, useState, useRef } from "react";
import { useRouter } from "next/navigation";
import { SpectechWebSocket } from "@/lib/websocket";
import { getAccessToken } from "@/lib/api";

interface LogEntry {
  id: string;
  time: string;
  type: string;
  direction: "in" | "out";
  data: any;
}

export default function WebSocketTestPage() {
  const router = useRouter();
  const [connected, setConnected] = useState(false);
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [pingTime, setPingTime] = useState<number | null>(null);
  const [stats, setStats] = useState<any>(null);
  const wsRef = useRef<SpectechWebSocket | null>(null);


  const addLog = (type: string, direction: "in" | "out", data: any) => {
  const newId = `${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
  setLogs((prev) => [
    {
      id: newId,
      time: new Date().toLocaleTimeString(),
      type,
      direction,
      data,
    },
    ...prev.slice(0, 99),
  ]);
};

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      router.push("/login");
      return;
    }

    const ws = new SpectechWebSocket(token, {
      onConnected: (data) => {
        setConnected(true);
        addLog("connected", "in", data);
      },
      onPong: (data) => {
        const sentTime = parseInt(localStorage.getItem("ping_sent") || "0");
        if (sentTime) {
          setPingTime(Date.now() - sentTime);
        }
        addLog("pong", "in", data);
      },
      onGpsPoint: (data) => addLog("gps_point", "in", data),
      onAlert: (data) => addLog("alert", "in", data),
      onRequestStatus: (data) => addLog("request_status", "in", data),
      onStats: (data) => {
        setStats(data.data);
        addLog("stats", "in", data);
      },
      onError: (error) => addLog("error", "in", { error }),
      onDisconnected: () => {
        setConnected(false);
        addLog("disconnected", "in", {});
      },
    });

    ws.connect();
    wsRef.current = ws;

    return () => {
      ws.disconnect();
    };
  }, []);

  const sendPing = () => {
    localStorage.setItem("ping_sent", Date.now().toString());
    wsRef.current?.send({ type: "ping" });
    addLog("ping", "out", {});
  };

  const requestStats = () => {
    wsRef.current?.requestStats();
    addLog("stats_request", "out", {});
  };

  const subscribe = (channel: "gps" | "alerts" | "requests") => {
    wsRef.current?.subscribe(channel);
    addLog("subscribe", "out", { channel });
  };

  return (
    <div className="min-h-screen bg-slate-50 p-6">
      <div className="max-w-6xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">
              📡 WebSocket Test Console
            </h1>
            <p className="text-sm text-slate-500 mt-1">
              Тестирование real-time коммуникации
            </p>
          </div>
          <button
            onClick={() => router.push("/dashboard")}
            className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-100"
          >
            ← Назад
          </button>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          {/* Status */}
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="text-sm text-slate-500 mb-2">Статус подключения</div>
            <div className="flex items-center gap-2">
              <div
                className={`w-3 h-3 rounded-full ${
                  connected ? "bg-green-500" : "bg-red-500"
                }`}
              />
              <span className="font-medium">
                {connected ? "Подключено" : "Отключено"}
              </span>
            </div>
            {pingTime !== null && (
              <div className="text-xs text-slate-500 mt-2">
                Пинг: <b>{pingTime}ms</b>
              </div>
            )}
          </div>

          {/* Stats */}
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="text-sm text-slate-500 mb-2">Статистика сервера</div>
            {stats ? (
              <div className="text-sm space-y-1">
                <div>
                  Всего подключений: <b>{stats.total_connections}</b>
                </div>
                <div>
                  Пользователей онлайн: <b>{stats.total_users}</b>
                </div>
                <div>
                  Компаний онлайн: <b>{stats.companies_online}</b>
                </div>
              </div>
            ) : (
              <div className="text-sm text-slate-400">Нет данных</div>
            )}
          </div>

          {/* Actions */}
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <div className="text-sm text-slate-500 mb-2">Действия</div>
            <div className="flex flex-wrap gap-2">
              <button
                onClick={sendPing}
                disabled={!connected}
                className="rounded bg-blue-600 px-3 py-1.5 text-xs text-white hover:bg-blue-700 disabled:bg-slate-300"
              >
                🏓 Ping
              </button>
              <button
                onClick={requestStats}
                disabled={!connected}
                className="rounded bg-indigo-600 px-3 py-1.5 text-xs text-white hover:bg-indigo-700 disabled:bg-slate-300"
              >
                📊 Stats
              </button>
              <button
                onClick={() => subscribe("gps")}
                disabled={!connected}
                className="rounded bg-green-600 px-3 py-1.5 text-xs text-white hover:bg-green-700 disabled:bg-slate-300"
              >
                📍 GPS
              </button>
              <button
                onClick={() => subscribe("alerts")}
                disabled={!connected}
                className="rounded bg-red-600 px-3 py-1.5 text-xs text-white hover:bg-red-700 disabled:bg-slate-300"
              >
                🚨 Alerts
              </button>
              <button
                onClick={() => subscribe("requests")}
                disabled={!connected}
                className="rounded bg-yellow-600 px-3 py-1.5 text-xs text-white hover:bg-yellow-700 disabled:bg-slate-300"
              >
                📋 Requests
              </button>
            </div>
          </div>
        </div>

        {/* Logs */}
        <div className="bg-white rounded-xl border border-slate-200 overflow-hidden">
          <div className="border-b border-slate-200 px-4 py-3 flex justify-between items-center">
            <h2 className="font-medium text-slate-900">
              📜 Лог сообщений ({logs.length})
            </h2>
            <button
              onClick={() => setLogs([])}
              className="text-xs text-slate-500 hover:text-slate-700"
            >
              Очистить
            </button>
          </div>
          <div className="max-h-[500px] overflow-y-auto">
            {logs.length === 0 ? (
              <div className="text-center text-slate-400 py-8">
                Нет сообщений
              </div>
            ) : (
              <table className="w-full text-xs">
                <thead className="bg-slate-50 sticky top-0">
                  <tr>
                    <th className="px-3 py-2 text-left">Время</th>
                    <th className="px-3 py-2 text-left">Направление</th>
                    <th className="px-3 py-2 text-left">Тип</th>
                    <th className="px-3 py-2 text-left">Данные</th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map((log) => (
                    <tr
                      key={log.id}
                      className={`border-t border-slate-100 ${
                        log.direction === "in" ? "bg-green-50" : "bg-blue-50"
                      }`}
                    >
                      <td className="px-3 py-2 font-mono text-slate-600">
                        {log.time}
                      </td>
                      <td className="px-3 py-2">
                        <span
                          className={`inline-block px-2 py-0.5 rounded text-xs ${
                            log.direction === "in"
                              ? "bg-green-200 text-green-800"
                              : "bg-blue-200 text-blue-800"
                          }`}
                        >
                          {log.direction === "in" ? "← IN" : "→ OUT"}
                        </span>
                      </td>
                      <td className="px-3 py-2 font-semibold">{log.type}</td>
                      <td className="px-3 py-2 font-mono text-slate-600 max-w-md overflow-hidden text-ellipsis">
                        {JSON.stringify(log.data).slice(0, 80)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
