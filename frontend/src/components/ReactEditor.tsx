import React, { useState, useEffect, useRef } from "react";
import { Chat } from "./Chat";
import { Panel } from "./Panel";

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
  const [activeRight, setActiveRight] = useState<"code" | "preview">("code");
  const [lastSavedPath, setLastSavedPath] = useState("");
  const [lastSavedCode, setLastSavedCode] = useState("");
  const isAutoSavingRef = useRef(false);

  const API_BASE = (import.meta as any).env.VITE_REACT_APP_API_URL + "/api";
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
    console.log("base url", API_BASE);
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

  // 파일 트리 갱신 (로딩 스피너 없이, 변경된 경우에만 반영)
  const fetchFileTreeSilently = async () => {
    try {
      const data = await apiCall("/files");
      const newTree = data.tree || [];
      // 내용이 동일하면 상태 업데이트 생략하여 리렌더/깜박임 방지
      const same = JSON.stringify(newTree) === JSON.stringify(fileTree);
      if (!same) {
        setFileTree(newTree);
      }
    } catch (e) {
      // 조용히 무시 (자동 폴링에서는 에러로 UI 깜박이지 않도록)
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
      // 방금 불러온 내용은 디스크와 동기화된 상태로 간주하여 즉시 저장 트리거를 방지
      setLastSavedPath(relativePath);
      setLastSavedCode(data.content ?? "");
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
      // 마지막 저장 시점 갱신
      setLastSavedPath(selectedFilePath);
      setLastSavedCode(code);
    } catch (error) {
      console.error("Error updating component:", error);
    }
  };

  // 코드 자동 저장: 입력이 멈춘 뒤 1.5초 후 저장 (파일 선택되어 있고 로딩 중이 아닐 때)
  useEffect(() => {
    if (!selectedFilePath) return;
    if (loadingFileContent) return;
    // 변경 없음 → 저장 생략
    if (selectedFilePath === lastSavedPath && code === lastSavedCode) return;

    const timer = setTimeout(async () => {
      if (isAutoSavingRef.current) return;
      try {
        isAutoSavingRef.current = true;
        await updateComponent();
      } catch (_) {
      } finally {
        isAutoSavingRef.current = false;
      }
    }, 1500);

    return () => clearTimeout(timer);
  }, [
    code,
    selectedFilePath,
    loadingFileContent,
    lastSavedPath,
    lastSavedCode,
  ]);

  // 채팅에서 파일 업데이트 처리
  const handleFileUpdate = async (filePath: string, newContent: string) => {
    try {
      // 파일 내용 업데이트
      await apiCall("/file", {
        method: "PUT",
        body: JSON.stringify({ relativePath: filePath, content: newContent }),
      });

      // 현재 선택된 파일이 업데이트된 파일과 같으면 에디터도 업데이트
      if (selectedFilePath === filePath) {
        setCode(newContent);
      }

      console.log("File updated by chat:", filePath);
    } catch (error) {
      console.error("Error updating file from chat:", error);
      setError("파일 업데이트 중 오류가 발생했습니다.");
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
    <div className="min-h-screen flex flex-col text-slate-200 bg-[#0b0f1a] h-[100vh]">
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
      {/* 본문 레이아웃: 좌측 Chat, 우측 코드/프리뷰 스위치 패널 */}

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

      <div className="flex flex-1 overflow-hidden h-[90vh]">
        {/* 왼쪽: Chat 패널 */}
        <div className="w-[360px] m-3 rounded-xl overflow-hidden bg-white/5 border border-white/10 flex flex-col min-h-0">
          <div className="px-4 py-3 border-b border-white/10 bg-white/5 font-semibold flex-shrink-0">
            Chat
          </div>
          <div className="flex-1 overflow-hidden p-3 min-h-0">
            <Chat
              selectedFilePath={selectedFilePath}
              fileContent={code}
              onFileUpdate={handleFileUpdate}
              onClearSelectedFile={() => setSelectedFilePath("")}
            />
          </div>
        </div>

        {/* 오른쪽: 코드/프리뷰 전환 패널 */}
        <Panel
          activeRight={activeRight}
          setActiveRight={setActiveRight}
          code={code}
          setCode={(v) => setCode(v)}
          fileTree={fileTree}
          loadingFiles={loadingFiles}
          selectedFilePath={selectedFilePath}
          loadingFileContent={loadingFileContent}
          devServerUrl={devServerUrl}
          isServerRunning={isServerRunning}
          loading={loading}
          routeInput={routeInput}
          setRouteInput={setRouteInput}
          routePath={routePath}
          setRoutePath={setRoutePath}
          fetchFileTree={fetchFileTree}
          loadFile={loadFile}
          runFullProcess={runFullProcess}
          updateComponent={updateComponent}
          stopDevServer={stopDevServer}
          buildPreviewUrl={buildPreviewUrl}
          iframeRef={iframeRef}
          configureMonaco={configureMonaco}
          refreshFileTreeSilently={fetchFileTreeSilently}
        />
      </div>
    </div>
  );
};

export default ReactEditor;
