import React, { useState, useEffect, useRef } from "react";
import "./ReactEditor.css";
import Editor from "@monaco-editor/react";
import { getLanguageFromPath } from "../utils/getLanguageFromPath";
import { RefreshCcw, Folder, FolderOpen, File as FileIcon } from "lucide-react";

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

// 간단한 트리뷰 컴포넌트
const TreeView = ({ nodes, onFileClick, selectedPath, basePath = "" }) => {
  return (
    <ul className="tree">
      {nodes.map((node) => {
        const fullPath = basePath ? `${basePath}/${node.name}` : node.name;
        if (node.type === "directory") {
          return (
            <li key={fullPath} className="tree-node dir">
              <details open>
                <summary>
                  <span className="icon-folder-closed" aria-hidden>
                    <Folder className="w-4 h-4 text-blue-500" />
                  </span>
                  <span className="icon-folder-open" aria-hidden>
                    <FolderOpen className="w-4 h-4 text-blue-500" />
                  </span>
                  {node.name}
                </summary>
                <TreeView
                  nodes={node.children || []}
                  onFileClick={onFileClick}
                  selectedPath={selectedPath}
                  basePath={fullPath}
                />
              </details>
            </li>
          );
        }
        const isSelected = selectedPath === fullPath;
        return (
          <li
            key={fullPath}
            className={`tree-node file ${isSelected ? "selected" : ""}`}
          >
            <button className="tree-file" onClick={() => onFileClick(fullPath)}>
              <FileIcon className="w-4 h-4 text-blue-500" />
              {node.name}
            </button>
          </li>
        );
      })}
    </ul>
  );
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
    <div className="react-editor">
      {/* 상단 툴바 */}
      <div className="toolbar">
        <h1>🚀 React Live Editor</h1>
        <div className="status">
          Status: {isServerRunning ? "🟢 Running" : "🔴 Stopped"}
          {devServerUrl && <span className="url"> - {devServerUrl}</span>}
        </div>
      </div>

      {/* 에러 표시 */}
      {error && (
        <div className="error-banner">
          ⚠️ {error}
          <button onClick={clearError} className="error-close">
            ×
          </button>
        </div>
      )}

      <div className="main-content">
        {/* 왼쪽 패널: 파일 트리 + 코드 에디터 */}
        <div className="editor-panel">
          <div className="panel-header">
            <h2>Code Editor</h2>
            <div className="button-group">
              <button
                onClick={runFullProcess}
                disabled={loading}
                className="btn btn-primary"
              >
                {loading ? "⏳ Setting up..." : "🚀 Initialize & Start"}
              </button>

              <button
                onClick={updateComponent}
                disabled={!isServerRunning || !selectedFilePath}
                className="btn btn-success"
              >
                💾 Save File
              </button>

              <button
                onClick={stopDevServer}
                disabled={!isServerRunning}
                className="btn btn-danger"
              >
                🛑 Stop Server
              </button>
            </div>
          </div>
          <div className="editor-area">
            {/* 파일 트리 섹션 */}
            <div className="file-tree-section">
              <div className="file-tree-header">
                <span>Files</span>
                <button
                  className="btn-refresh"
                  onClick={fetchFileTree}
                  title="Refresh file tree"
                >
                  <RefreshCcw size={16} aria-label="Refresh file tree" />
                </button>
              </div>
              <div className="file-tree">
                {loadingFiles ? (
                  <div className="tree-loading">Loading files...</div>
                ) : fileTree.length === 0 ? (
                  <div className="tree-empty">No files</div>
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
            <div className="editor-section">
              {/* 라우팅 경로 입력 바 */}
              <div
                className="route-bar"
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "6px 8px",
                  borderBottom: "1px solid #2a2a2a",
                }}
              >
                <span style={{ fontSize: 12, opacity: 0.8 }}>Route</span>
                <input
                  className="route-input"
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
                  style={{
                    flex: 1,
                    background: "#1e1e1e",
                    color: "#fff",
                    border: "1px solid #3a3a3a",
                    borderRadius: 4,
                    padding: "6px 8px",
                    fontSize: 12,
                  }}
                />
                <button
                  className="btn btn-primary"
                  onClick={() => {
                    const next = (routeInput || "/").trim();
                    setRoutePath(next.length === 0 ? "/" : next);
                  }}
                  title="Apply route"
                >
                  Go
                </button>
              </div>
              <div className="selected-file-bar">
                <span className="selected-file-path">
                  {selectedFilePath || "Select a file from the tree"}
                </span>
                {loadingFileContent && <span className="loading-dot">●</span>}
              </div>
              <div className="code-editor-wrapper">
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
        <div className="preview-panel">
          <div className="panel-header">
            <h2>Live Preview</h2>
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
                className="btn-refresh"
              >
                <RefreshCcw size={16} aria-label="Refresh preview" />
              </button>
            )}
          </div>

          {devServerUrl ? (
            <iframe
              ref={iframeRef}
              src={buildPreviewUrl(devServerUrl, routePath)}
              className="preview-iframe"
              title="React Preview"
              sandbox="allow-scripts allow-same-origin"
            />
          ) : (
            <div className="preview-placeholder">
              {loading ? (
                <div className="loading">
                  <div className="spinner"></div>
                  <p>Starting development server...</p>
                </div>
              ) : (
                <div className="welcome-message">
                  <h3>🎨 Welcome to React Live Editor!</h3>
                  <p>Click "Initialize & Start" to begin coding</p>
                  <div className="features">
                    <div>✨ Real-time preview</div>
                    <div>🔄 Hot reload</div>
                    <div>📱 Responsive design</div>
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
