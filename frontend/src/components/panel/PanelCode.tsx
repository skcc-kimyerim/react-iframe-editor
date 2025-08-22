import React, { useEffect } from "react";
import Editor from "@monaco-editor/react";
import { RefreshCcw } from "lucide-react";
import { TreeView } from "../TreeView";
import { getLanguageFromPath } from "../../utils/getLanguageFromPath";

type Props = {
  fileTree: any[];
  loadingFiles: boolean;
  fetchFileTree: () => Promise<void>;
  refreshFileTreeSilently: () => Promise<void>;
  selectedFilePath: string;
  loadFile: (relativePath: string) => Promise<void>;
  loadingFileContent: boolean;
  code: string;
  setCode: (v: string) => void;
  configureMonaco: (monaco: any) => void;
};

export const PanelCode: React.FC<Props> = ({
  fileTree,
  loadingFiles,
  fetchFileTree,
  refreshFileTreeSilently,
  selectedFilePath,
  loadFile,
  loadingFileContent,
  code,
  setCode,
  configureMonaco,
}) => {
  // 파일 트리 자동 새로고침 (7초 간격)
  useEffect(() => {
    let stopped = false;
    let timerId: number | undefined;

    const schedule = (delayMs: number) => {
      if (stopped) return;
      timerId = window.setTimeout(tick, delayMs);
    };

    const tick = async () => {
      try {
        // 로딩 스피너 없이 조용히 동기화 (리스트 변경 시에만 상태 갱신)
        await refreshFileTreeSilently();
      } catch (_) {
      } finally {
        schedule(7000);
      }
    };

    const handleVisibility = () => {
      if (document.visibilityState === "visible") {
        if (timerId == null) schedule(0);
      } else if (timerId != null) {
        clearTimeout(timerId);
        timerId = undefined;
      }
    };

    if (document.visibilityState === "visible") schedule(0);
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      stopped = true;
      if (timerId != null) clearTimeout(timerId);
      document.removeEventListener("visibilitychange", handleVisibility);
    };
  }, [refreshFileTreeSilently]);

  return (
    <div className="flex flex-1 min-h-0">
      {/* 파일 트리 섹션 */}
      <div className="w-[280px] border-r border-white/10 flex flex-col bg-white/5 min-h-0">
        <div className="flex items-center justify-between px-3 py-2 border-b border-white/10 bg-white/5 font-semibold flex-shrink-0">
          <span>Files</span>
          <button
            className="px-2 py-1 text-xs rounded-md border border-white/15 text-slate-200 hover:bg-white/10"
            onClick={fetchFileTree}
            title="Refresh file tree"
          >
            <RefreshCcw size={16} aria-label="Refresh file tree" />
          </button>
        </div>
        <div className="p-2 pb-3 overflow-y-auto overflow-x-hidden flex-1 min-h-0 scrollbar-hide">
          {loadingFiles ? (
            <div className="text-sm text-slate-400 px-3 py-2">
              Loading files...
            </div>
          ) : fileTree.length === 0 ? (
            <div className="text-sm text-slate-400 px-3 py-2">No files</div>
          ) : (
            <TreeView
              nodes={fileTree}
              selectedPath={selectedFilePath}
              onFileClick={loadFile}
            />
          )}
        </div>
      </div>

      {/* 코드 에디터 섹션 */}
      <div className="flex flex-1 flex-col min-w-0 min-h-0">
        <div className="flex items-center justify-between px-3 py-3 border-b border-white/10 bg-white/5 font-mono text-xs text-slate-300 flex-shrink-0">
          <span>{selectedFilePath || "Select a file from the tree"}</span>
          {loadingFileContent && <span className="text-cyan-400">●</span>}
        </div>
        <div className="flex-1 min-h-0 overflow-hidden">
          <Editor
            value={code}
            onChange={(value) => setCode(value ?? "")}
            language={getLanguageFromPath(selectedFilePath)}
            beforeMount={configureMonaco}
            path={selectedFilePath || "file:///index.tsx"}
            theme="vs-dark"
            height="100%"
            width="100%"
            options={{
              fontSize: 14,
              minimap: { enabled: false },
              wordWrap: "on",
              automaticLayout: true,
              tabSize: 2,
              scrollBeyondLastLine: false,
            }}
          />
        </div>
      </div>
    </div>
  );
};
