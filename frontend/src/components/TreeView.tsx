// 간단한 트리뷰 컴포넌트 (Tailwind-only)
import React, { useState } from "react";
import { Folder, FolderOpen, File as FileIcon } from "lucide-react";

type TreeNode = {
  name: string;
  type: "directory" | "file";
  children?: TreeNode[];
};

type TreeViewProps = {
  nodes: TreeNode[];
  onFileClick: (path: string) => void;
  selectedPath?: string;
  basePath?: string;
};

const DirectoryNode: React.FC<{
  node: TreeNode;
  basePath: string;
  onFileClick: (path: string) => void;
  selectedPath?: string;
}> = ({ node, basePath, onFileClick, selectedPath }) => {
  const [isOpen, setIsOpen] = useState(true);
  const fullPath = basePath ? `${basePath}/${node.name}` : node.name;

  return (
    <li className="my-0.5">
      <button
        type="button"
        onClick={() => setIsOpen((s) => !s)}
        className="w-full text-left flex items-center gap-1.5 px-1.5 py-1 rounded-md font-semibold text-slate-200 hover:bg-white/10"
      >
        {isOpen ? (
          <FolderOpen className="w-4 h-4 text-blue-500" />
        ) : (
          <Folder className="w-4 h-4 text-blue-500" />
        )}
        {node.name}
      </button>
      {isOpen && node.children && node.children.length > 0 && (
        <ul className="list-none pl-3 m-0">
          <TreeView
            nodes={node.children}
            onFileClick={onFileClick}
            selectedPath={selectedPath}
            basePath={fullPath}
          />
        </ul>
      )}
    </li>
  );
};

export const TreeView: React.FC<TreeViewProps> = ({
  nodes,
  onFileClick,
  selectedPath,
  basePath = "",
}) => {
  return (
    <ul className="list-none pl-3 m-0">
      {nodes.map((node) => {
        const fullPath = basePath ? `${basePath}/${node.name}` : node.name;
        if (node.type === "directory") {
          return (
            <DirectoryNode
              key={fullPath}
              node={node}
              basePath={basePath}
              onFileClick={onFileClick}
              selectedPath={selectedPath}
            />
          );
        }
        const isSelected = selectedPath === fullPath;
        return (
          <li key={fullPath} className="my-0.5">
            <button
              className={`w-full text-left flex items-center gap-1.5 px-1.5 py-1 rounded-md text-slate-300 hover:bg-white/10 ${
                isSelected ? "bg-white/15 text-slate-100" : ""
              }`}
              onClick={() => onFileClick(fullPath)}
            >
              <FileIcon className="w-4 h-4 text-blue-500" />
              {node.name}
            </button>
          </li>
        );
      })}
    </ul>
  );
};
