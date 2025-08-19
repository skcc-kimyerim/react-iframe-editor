import React, { useEffect, useMemo, useRef, useState } from "react";
import { Terminal, ChevronDown, ChevronRight } from "lucide-react";

type Props = {
  devServerUrl: string;
  routePath: string;
  buildPreviewUrl: (baseUrl: string, path: string) => string;
  iframeRef: React.RefObject<HTMLIFrameElement>;
  loading: boolean;
};

export const PanelPreview: React.FC<Props> = ({
  devServerUrl,
  routePath,
  buildPreviewUrl,
  iframeRef,
  loading,
}) => {
  const [isTerminalOpen, setIsTerminalOpen] = useState(false);
  const [logs, setLogs] = useState<any[]>([]);
  const wsRef = useRef<WebSocket | null>(null);

  // ANSI 컬러/제어 시퀀스 제거
  const stripAnsi = (input: string): string => {
    if (!input) return "";
    const ansiPattern =
      /[\u001B\u009B][[\]()#;?]*(?:[0-9]{1,4}(?:;[0-9]{0,4})*)?[0-9A-ORZcf-nqry=><]/g;
    return input.replace(ansiPattern, "");
  };

  // WebSocket 연결 관리
  useEffect(() => {
    // dev 서버가 없으면 연결하지 않음
    if (!devServerUrl) return;

    const API_HTTP =
      (import.meta as any).env?.VITE_REACT_APP_API_URL ||
      window.location.origin;
    const WS_URL =
      String(API_HTTP).replace(/^http/i, "ws") + "/api/dev-server/logs";

    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;
      ws.onopen = () => {
        // 연결됨
      };
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data && data.type === "log") {
            setLogs((prev) => {
              const next = [
                ...prev,
                {
                  id: String(Date.now()) + ":" + String(prev.length + 1),
                  time: data.time ?? Date.now(),
                  level:
                    data.level || (data.stream === "stderr" ? "error" : "info"),
                  stream: data.stream,
                  text: stripAnsi(String(data.text ?? "")),
                },
              ];
              return next.length > 1000 ? next.slice(next.length - 1000) : next;
            });
          }
        } catch (_) {}
      };
      ws.onerror = () => {
        // 오류는 무시하고 유지
      };
      ws.onclose = () => {
        wsRef.current = null;
      };
    } catch (_) {}

    return () => {
      try {
        wsRef.current?.close();
      } catch (_) {}
      wsRef.current = null;
    };
  }, [devServerUrl]);

  const clearLogs = () => setLogs([]);

  if (devServerUrl) {
    return (
      <div className="flex-1 min-h-0 overflow-hidden flex flex-col">
        <div className="flex-1 min-h-0">
          <iframe
            ref={iframeRef}
            src={buildPreviewUrl(devServerUrl, routePath)}
            className="w-full h-full border-0 bg-white"
            title="React Preview"
            sandbox="allow-scripts allow-same-origin allow-forms allow-modals allow-popups"
          />
        </div>

        <div className="border-t border-white/10 bg-black/40 text-xs text-slate-200">
          <div className="flex items-center justify-between px-3 py-1.5">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsTerminalOpen((v) => !v)}
                className="px-2 py-0.5 text-[14px] rounded-md border border-white/15 hover:bg-white/10 flex items-center gap-1"
                aria-expanded={isTerminalOpen}
                aria-label="Toggle terminal"
                title="Terminal (dev server)"
              >
                <Terminal size={14} />
                <span className="hidden sm:inline">Terminal</span>
              </button>
              <span className="opacity-70">{logs.length}</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={clearLogs}
                className="px-2 py-0.5 text-[11px] rounded-md border border-white/15 hover:bg-white/10"
              >
                Clear
              </button>
            </div>
          </div>
          {isTerminalOpen && (
            <div className="max-h-72 overflow-auto px-3 py-2 space-y-1 scrollbar-hide font-mono">
              {logs.length === 0 ? (
                <div className="opacity-60">No output</div>
              ) : (
                logs.map((l) => (
                  <div
                    key={l.id}
                    className={
                      "whitespace-pre-wrap break-words " +
                      (l.level === "error"
                        ? "text-red-300"
                        : l.level === "warn"
                        ? "text-yellow-300"
                        : l.level === "info"
                        ? "text-sky-300"
                        : "text-slate-200")
                    }
                  >
                    <span className="opacity-50 mr-2">
                      {new Date(l.time).toLocaleTimeString()}
                    </span>
                    <span className="uppercase mr-2 opacity-80">{l.level}</span>
                    <span>{l.text}</span>
                  </div>
                ))
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 flex items-center justify-center bg-white/5 text-slate-300 text-center min-h-0 overflow-y-auto">
      {loading ? (
        <div className="flex flex-col items-center gap-5">
          <div className="w-10 h-10 border-4 border-white/10 border-t-cyan-400 rounded-full animate-spin"></div>
          <p>Starting development server...</p>
        </div>
      ) : (
        <div>
          <h3 className="text-slate-100 mb-2">
            🎨 Welcome to React Live Editor!
          </h3>
          <p className="text-base mb-5 text-slate-300">
            Click "Initialize & Start" to begin coding
          </p>
          <div className="flex flex-col gap-2 text-sm">
            <div className="inline-block bg-white/10 border border-white/10 px-4 py-2 rounded-full">
              ✨ Real-time preview
            </div>
            <div className="inline-block bg-white/10 border border-white/10 px-4 py-2 rounded-full">
              🔄 Hot reload
            </div>
            <div className="inline-block bg-white/10 border border-white/10 px-4 py-2 rounded-full">
              📱 Responsive design
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
