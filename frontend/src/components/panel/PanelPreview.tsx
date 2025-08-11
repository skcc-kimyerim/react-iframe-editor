import React from "react";

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
  if (devServerUrl) {
    return (
      <div className="flex-1 min-h-0 overflow-hidden">
        <iframe
          ref={iframeRef}
          src={buildPreviewUrl(devServerUrl, routePath)}
          className="w-full h-full border-0 bg-white"
          title="React Preview"
          sandbox="allow-scripts allow-same-origin"
        />
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
