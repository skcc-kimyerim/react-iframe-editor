import React from "react";

type ActiveTab = "code" | "preview";

type Props = {
  activeRight: ActiveTab;
  setActiveRight: (t: ActiveTab) => void;
  loading: boolean;
  isServerRunning: boolean;
  selectedFilePath: string;
  routeInput: string;
  setRouteInput: (v: string) => void;
  routePath: string;
  setRoutePath: (v: string) => void;
  runFullProcess: () => Promise<void>;
  updateComponent: () => Promise<void>;
  stopDevServer: () => Promise<void>;
};

export const PanelHeader: React.FC<Props> = ({
  activeRight,
  setActiveRight,
  loading,
  isServerRunning,
  selectedFilePath,
  routeInput,
  setRouteInput,
  routePath,
  setRoutePath,
  runFullProcess,
  updateComponent,
  stopDevServer,
}) => {
  return (
    <div className="flex items-center justify-between gap-3 px-4 py-3 border-b border-white/10 bg-white/5">
      {/* 탭 */}
      <div className="flex items-center gap-2">
        <button
          className={`px-3 py-1.5 text-sm rounded-md border ${
            activeRight === "code"
              ? "bg-indigo-600 text-white border-transparent"
              : "bg-transparent text-slate-200 border-white/15 hover:bg-white/10"
          }`}
          onClick={() => setActiveRight("code")}
        >
          Code
        </button>
        <button
          className={`px-3 py-1.5 text-sm rounded-md border ${
            activeRight === "preview"
              ? "bg-indigo-600 text-white border-transparent"
              : "bg-transparent text-slate-200 border-white/15 hover:bg-white/10"
          }`}
          onClick={() => setActiveRight("preview")}
        >
          Preview
        </button>
      </div>

      {/* 액션 버튼 */}
      <div className="flex items-center gap-2">
        <button
          onClick={runFullProcess}
          disabled={loading}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-md text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60 disabled:cursor-not-allowed text-sm font-semibold border border-transparent"
        >
          {loading ? "⏳ Setting up..." : "🚀 Initialize & Start"}
        </button>
        <button
          onClick={updateComponent}
          disabled={!isServerRunning || !selectedFilePath}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-md text-white bg-green-600 hover:bg-green-700 disabled:opacity-60 text-sm font-semibold border border-transparent"
        >
          💾 Save File
        </button>
        <button
          onClick={stopDevServer}
          disabled={!isServerRunning}
          className="inline-flex items-center gap-2 px-3 py-2 rounded-md text-white bg-red-500 hover:bg-red-600 disabled:opacity-60 text-sm font-semibold border border-transparent"
        >
          🛑 Stop Server
        </button>
      </div>

      {/* Route 입력 */}
      <div className="flex items-center gap-2 min-w-[220px]">
        <span className="text-xs opacity-80">Route</span>
        <input
          className="flex-1 bg-[#0f121f] text-white border border-white/10 rounded px-2 py-1 text-xs focus:outline-none focus:border-cyan-400/60 focus:ring-2 focus:ring-cyan-400/20"
          value={routeInput}
          onChange={(e) => setRouteInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              const next = (routeInput || "/").trim();
              setRoutePath(next.length === 0 ? "/" : next);
            }
          }}
          onBlur={() => {
            const next = (routeInput || "/").trim();
            setRoutePath(next.length === 0 ? "/" : next);
          }}
          placeholder="/"
        />
        <button
          className="inline-flex items-center px-3 py-1.5 rounded-md text-white bg-indigo-600 hover:bg-indigo-700 text-sm font-semibold"
          onClick={() => {
            const next = (routeInput || "/").trim();
            setRoutePath(next.length === 0 ? "/" : next);
          }}
          title="Apply route"
        >
          Go
        </button>
      </div>
    </div>
  );
};
