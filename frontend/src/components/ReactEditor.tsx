import React, { useState, useEffect, useRef } from "react";
import Editor from "@monaco-editor/react";
import { getLanguageFromPath } from "../utils/getLanguageFromPath";
import { RefreshCcw } from "lucide-react";
import { TreeView } from "./TreeView";

// Monaco TypeScript 설정: 브라우저 환경에서 모듈 해석이 어려워 생기는
// 과도한 오류(react 등 모듈을 찾지 못함)를 줄이기 위한 설정
const configureMonaco = (monaco) => {
  // JSX 및 기본 TS 컴파일러 옵션 설정
  monaco.languages.typescript.typescriptDefaults.setCompilerOptions({
    jsx: monaco.languages.typescript.JsxEmit.ReactJSX,
    allowJs: true,
    allowNonTsExtensions: true,
    target: monaco.languages.typescript.ScriptTarget.ES2020,
    module: monaco.languages.typescript.ModuleKind.ESNext,
    moduleResolution: monaco.languages.typescript.ModuleResolutionKind.NodeJs,
    esModuleInterop: true,
    skipLibCheck: true,
    noEmit: true,
  });

  // 모듈 타입 정보를 모두 불러올 수 없어 생기는 빨간줄을 완화
  monaco.languages.typescript.typescriptDefaults.setDiagnosticsOptions({
    noSemanticValidation: true,
    noSyntaxValidation: false,
  });
};

const ReactEditor = () => {
  const [code, setCode] = useState("");
  const [fileTree, setFileTree] = useState([]);
  const [selectedFilePath, setSelectedFilePath] = useState("");
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [loadingFileContent, setLoadingFileContent] = useState(false);
  const [devServerUrl, setDevServerUrl] = useState("");
  const [isServerRunning, setIsServerRunning] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const iframeRef = useRef(null);
  const [routePath, setRoutePath] = useState("/");
  const [routeInput, setRouteInput] = useState("/");

  const API_BASE = "http://localhost:3001/api";
  // routePath가 변경되면 입력값 동기화
  useEffect(() => {
    setRouteInput(routePath || "/");
  }, [routePath]);

  const buildPreviewUrl = (baseUrl, path) => {
    if (!baseUrl) return "";
    const normalizedBase = baseUrl.replace(/\/+$/, "");
    let normalizedPath = (path || "/").trim();
    if (!normalizedPath.startsWith("/")) normalizedPath = "/" + normalizedPath;
    return normalizedBase + normalizedPath;
  };

  // devServerUrl 또는 routePath 변경 시 iframe 갱신
  useEffect(() => {
    if (isServerRunning && iframeRef.current && devServerUrl) {
      iframeRef.current.src = buildPreviewUrl(devServerUrl, routePath);
    }
  }, [devServerUrl, routePath, isServerRunning]);

  // 에러 클리어
  const clearError = () => setError("");

  // API 호출 헬퍼 함수
  const apiCall = async (endpoint, options = {}) => {
    try {
      const response = await fetch(`${API_BASE}${endpoint}`, {
        headers: { "Content-Type": "application/json" },
        ...options,
      });

      if (!response.ok) {
        throw new Error(`API Error: ${response.statusText}`);
      }

      return await response.json();
    } catch (error) {
      console.error("API call failed:", error);
      setError(error.message);
      throw error;
    }
  };

  // 프로젝트 초기화
  const initializeProject = async () => {
    console.log("Initializing project...");
    await apiCall("/init-project", {
      method: "POST",
      body: JSON.stringify({
        componentCode: code,
        dependencies: {},
      }),
    });
    console.log("Project initialized successfully");
    await fetchFileTree();
  };

  // React 개발 서버 시작
  const startDevServer = async () => {
    console.log("Starting development server...");
    const data = await apiCall("/start-dev-server", {
      method: "POST",
    });

    setDevServerUrl(data.devServerUrl);
    setIsServerRunning(true);

    // iframe 로드를 위한 딜레이
    setTimeout(() => {
      if (iframeRef.current) {
        iframeRef.current.src = buildPreviewUrl(data.devServerUrl, routePath);
      }
    }, 3000);

    console.log("Development server started:", data.devServerUrl);
    await fetchFileTree();
  };

  // React 개발 서버 중지
  const stopDevServer = async () => {
    try {
      await apiCall("/stop-dev-server", {
        method: "POST",
      });
      setIsServerRunning(false);
      setDevServerUrl("");
      if (iframeRef.current) {
        iframeRef.current.src = "";
      }
      console.log("Development server stopped");
    } catch (error) {
      console.error("Error stopping dev server:", error);
    }
  };

  // 파일 트리 가져오기
  const fetchFileTree = async () => {
    try {
      setLoadingFiles(true);
      const data = await apiCall("/files");
      console.log(data);
      setFileTree(data.tree || []);
    } catch (e) {
      console.error("Error fetching file tree:", e);
    } finally {
      setLoadingFiles(false);
    }
  };

  // 파일 내용 불러오기
  const loadFile = async (relativePath) => {
    try {
      clearError();
      setLoadingFileContent(true);
      const data = await apiCall(
        `/file?relativePath=${encodeURIComponent(relativePath)}`
      );
      setCode(data.content ?? "");
      setSelectedFilePath(relativePath);
    } catch (e) {
      console.error("Error loading file:", e);
    } finally {
      setLoadingFileContent(false);
    }
  };

  // 현재 선택 파일 저장
  const updateComponent = async () => {
    try {
      clearError();
      if (!selectedFilePath) {
        setError("저장할 파일을 좌측 트리에서 선택해주세요.");
        return;
      }
      await apiCall("/file", {
        method: "PUT",
        body: JSON.stringify({ relativePath: selectedFilePath, content: code }),
      });
      console.log("Component updated successfully");
    } catch (error) {
      console.error("Error updating component:", error);
    }
  };

  // 전체 프로세스 실행
  const runFullProcess = async () => {
    setLoading(true);
    clearError();

    try {
      await initializeProject();
      await new Promise((resolve) => setTimeout(resolve, 2000));
      await startDevServer();
    } catch (error) {
      console.error("Error in full process:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col text-slate-200 bg-[#0b0f1a]">
      {/* 상단 툴바 */}
      <div className="flex justify-between items-center px-5 py-4 border-b border-white/10 bg-white/5 backdrop-blur supports-[backdrop-filter]:bg-white/5">
        <h1 className="m-0 text-lg font-bold bg-clip-text text-transparent bg-gradient-to-r from-violet-300 to-cyan-300">
          🚀 React Live Editor
        </h1>
        <div className="flex items-center gap-2 text-indigo-100">
          Status: {isServerRunning ? "🟢 Running" : "🔴 Stopped"}
          {devServerUrl && (
            <span className="text-sm opacity-80"> - {devServerUrl}</span>
          )}
        </div>
      </div>

      {/* 에러 표시 */}
      {error && (
        <div className="flex justify-between items-center px-4 py-3 border-y border-white/10 bg-red-500/10 text-red-200">
          ⚠️ {error}
          <button
            onClick={clearError}
            className="text-red-200 hover:text-red-100 text-lg px-1"
          >
            ×
          </button>
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        {/* 왼쪽 패널: 파일 트리 + 코드 에디터 */}
        <div className="flex flex-col m-3 rounded-xl overflow-hidden bg-white/5 border border-white/10">
          <div className="flex justify-between items-center px-4 py-3 border-b border-white/10 bg-white/5">
            <h2 className="m-0 text-base font-bold bg-clip-text text-transparent bg-gradient-to-r from-violet-300 to-cyan-300">
              Code Editor
            </h2>
            <div className="flex gap-2">
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
          </div>
          <div className="flex flex-1 min-h-0">
            {/* 파일 트리 섹션 */}
            <div className="w-[280px] border-r border-white/10 flex flex-col bg-white/5">
              <div className="flex items-center justify-between px-3 py-2 border-b border-white/10 bg-white/5 font-semibold">
                <span>Files</span>
                <button
                  className="px-2 py-1 text-xs rounded-md border border-white/15 text-slate-200 hover:bg-white/10"
                  onClick={fetchFileTree}
                  title="Refresh file tree"
                >
                  <RefreshCcw size={16} aria-label="Refresh file tree" />
                </button>
              </div>
              <div className="p-2 pb-3 overflow-auto flex-1">
                {loadingFiles ? (
                  <div className="text-sm text-slate-400 px-3 py-2">
                    Loading files...
                  </div>
                ) : fileTree.length === 0 ? (
                  <div className="text-sm text-slate-400 px-3 py-2">
                    No files
                  </div>
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
            <div className="flex flex-1 flex-col min-w-0">
              {/* 라우팅 경로 입력 바 */}
              <div className="flex items-center gap-2 px-2 py-1.5 border-b border-white/10 bg-white/5">
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
              <div className="flex items-center justify-between px-3 py-2 border-b border-white/10 bg-white/5 font-mono text-xs text-slate-300">
                <span>{selectedFilePath || "Select a file from the tree"}</span>
                {loadingFileContent && <span className="text-cyan-400">●</span>}
              </div>
              <div className="flex-1 min-h-0">
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
        </div>

        {/* 오른쪽 패널: iframe 프리뷰 */}
        <div className="flex flex-col m-3 rounded-xl overflow-hidden bg-white/5 border border-white/10">
          <div className="flex justify-between items-center px-4 py-3 border-b border-white/10 bg-white/5">
            <h2 className="m-0 text-base font-bold bg-clip-text text-transparent bg-gradient-to-r from-violet-300 to-cyan-300">
              Live Preview
            </h2>
            {devServerUrl && (
              <button
                onClick={() => {
                  if (iframeRef.current) {
                    iframeRef.current.src = buildPreviewUrl(
                      devServerUrl,
                      routePath
                    );
                  }
                }}
                className="px-2 py-1 text-xs rounded-md border border-white/15 text-slate-200 hover:bg-white/10"
              >
                <RefreshCcw size={16} aria-label="Refresh preview" />
              </button>
            )}
          </div>

          {devServerUrl ? (
            <iframe
              ref={iframeRef}
              src={buildPreviewUrl(devServerUrl, routePath)}
              className="w-full h-full flex-1 border-0 bg-[#0b0f1a]"
              title="React Preview"
              sandbox="allow-scripts allow-same-origin"
            />
          ) : (
            <div className="flex-1 flex items-center justify-center bg-white/5 text-slate-300 text-center">
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
          )}
        </div>
      </div>
    </div>
  );
};

export default ReactEditor;
