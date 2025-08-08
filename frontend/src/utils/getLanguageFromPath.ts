// 파일 경로에서 Monaco Editor 언어 감지
export const getLanguageFromPath = (filePath) => {
  if (!filePath || typeof filePath !== "string") return "javascript";
  const baseName = filePath.split("/").pop() || filePath;
  const lowerBase = baseName.toLowerCase();
  const lastDotIndex = lowerBase.lastIndexOf(".");
  const ext = lastDotIndex !== -1 ? lowerBase.slice(lastDotIndex + 1) : "";

  // 확장자 없이 파일명으로 판단해야 하는 케이스
  if (lowerBase === "dockerfile" || lowerBase.startsWith("dockerfile"))
    return "dockerfile";
  if (lowerBase === "makefile") return "makefile";

  switch (ext) {
    case "js":
    case "mjs":
    case "cjs":
    case "jsx":
      return "javascript";
    case "ts":
    case "tsx":
      return "typescript";
    case "json":
      return "json";
    case "css":
      return "css";
    case "scss":
      return "scss";
    case "less":
      return "less";
    case "html":
    case "htm":
      return "html";
    case "md":
    case "markdown":
      return "markdown";
    case "yml":
    case "yaml":
      return "yaml";
    case "sh":
    case "bash":
      return "shell";
    case "py":
      return "python";
    case "java":
      return "java";
    case "go":
      return "go";
    case "rs":
      return "rust";
    case "php":
      return "php";
    case "rb":
      return "ruby";
    case "sql":
      return "sql";
    case "xml":
    case "svg":
      return "xml";
    case "ini":
      return "ini";
    case "toml":
      return "toml";
    case "txt":
      return "plaintext";
    default:
      return "plaintext";
  }
};
