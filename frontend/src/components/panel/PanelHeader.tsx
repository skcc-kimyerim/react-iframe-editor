import React from "react";
import { RouteDropdown } from "./RouteDropdown";

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
  availableRoutes: string[];
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
  availableRoutes,
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

      {/* Route 선택 */}
      <RouteDropdown
        label="Route"
        value={routeInput}
        options={availableRoutes.length > 0 ? availableRoutes : ["/"]}
        onChange={(next) => {
          const v = (next || "/").trim();
          setRouteInput(v);
          setRoutePath(v.length === 0 ? "/" : v);
        }}
      />
    </div>
  );
};
