import React from "react";
import { PanelHeader } from "./panel/PanelHeader";
import { PanelCode } from "./panel/PanelCode";
import { PanelPreview } from "./panel/PanelPreview";

type ActiveTab = "code" | "preview";

type Props = {
  activeRight: ActiveTab;
  setActiveRight: (t: ActiveTab) => void;
  code: string;
  setCode: (v: string) => void;
  fileTree: any[];
  loadingFiles: boolean;
  selectedFilePath: string;
  loadingFileContent: boolean;
  devServerUrl: string;
  isServerRunning: boolean;
  loading: boolean;
  routeInput: string;
  setRouteInput: (v: string) => void;
  routePath: string;
  setRoutePath: (v: string) => void;
  availableRoutes: string[];
  fetchFileTree: () => Promise<void>;
  loadFile: (relativePath: string) => Promise<void>;
  runFullProcess: () => Promise<void>;
  updateComponent: () => Promise<void>;
  stopDevServer: () => Promise<void>;
  buildPreviewUrl: (baseUrl: string, path: string) => string;
  iframeRef: React.RefObject<HTMLIFrameElement>;
  configureMonaco: (monaco: any) => void;
  refreshFileTreeSilently: () => Promise<void>;
};

export const Panel: React.FC<Props> = ({
  activeRight,
  setActiveRight,
  code,
  setCode,
  fileTree,
  loadingFiles,
  selectedFilePath,
  loadingFileContent,
  devServerUrl,
  isServerRunning,
  loading,
  routeInput,
  setRouteInput,
  routePath,
  setRoutePath,
  availableRoutes,
  fetchFileTree,
  loadFile,
  runFullProcess,
  updateComponent,
  stopDevServer,
  buildPreviewUrl,
  iframeRef,
  configureMonaco,
  refreshFileTreeSilently,
}) => {
  return (
    <div className="flex flex-1 flex-col m-3 rounded-xl overflow-hidden bg-white/5 border border-white/10 min-w-0">
      <PanelHeader
        activeRight={activeRight}
        setActiveRight={setActiveRight}
        loading={loading}
        isServerRunning={isServerRunning}
        selectedFilePath={selectedFilePath}
        routeInput={routeInput}
        setRouteInput={setRouteInput}
        routePath={routePath}
        setRoutePath={setRoutePath}
        availableRoutes={availableRoutes}
        runFullProcess={runFullProcess}
        updateComponent={updateComponent}
        stopDevServer={stopDevServer}
      />

      {activeRight === "code" ? (
        <PanelCode
          fileTree={fileTree}
          loadingFiles={loadingFiles}
          fetchFileTree={fetchFileTree}
          refreshFileTreeSilently={refreshFileTreeSilently}
          selectedFilePath={selectedFilePath}
          loadFile={loadFile}
          loadingFileContent={loadingFileContent}
          code={code}
          setCode={setCode}
          configureMonaco={configureMonaco}
        />
      ) : (
        <PanelPreview
          devServerUrl={devServerUrl}
          routePath={routePath}
          buildPreviewUrl={buildPreviewUrl}
          iframeRef={iframeRef}
          loading={loading}
        />
      )}
    </div>
  );
};
