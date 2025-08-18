import React, { useEffect, useRef, useState } from "react";
import { File, Paperclip, Send, Trash2, X } from "lucide-react";
import { useProjectStore, Message } from "../stores/projectStore";

const API_BASE = (import.meta as any).env.VITE_REACT_APP_API_URL + "/api";

interface ChatProps {
  selectedFilePath?: string;
  fileContent?: string;
  onFileUpdate?: (filePath: string, content: string) => void;
  onClearSelectedFile?: () => void;
}

export const Chat: React.FC<ChatProps> = ({
  selectedFilePath,
  fileContent,
  onFileUpdate,
  onClearSelectedFile,
}) => {
  const { currentProject, addMessage } = useProjectStore();
  const messages = currentProject?.chatHistory || [];
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const isProcessingRef = useRef<boolean>(false); // API 호출 중복 방지
  const fileInputRef = useRef<HTMLInputElement>(null);

  type LocalAttachment = {
    id: string;
    file?: File;
    previewUrl?: string;
    uploaded?: {
      url: string;
      name?: string;
      mime?: string;
      size?: number;
      stored?: string;
    };
    error?: string;
  };
  const [attachments, setAttachments] = useState<LocalAttachment[]>([]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight });
  }, [messages, isSending]);

  useEffect(() => {
    if (inputRef.current) {
      autoSize();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const autoSize = () => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    const max = 160; // px
    el.style.height = Math.min(el.scrollHeight, max) + "px";
  };

  const onPickFiles = () => fileInputRef.current?.click();

  const onFilesSelected: React.ChangeEventHandler<HTMLInputElement> = (e) => {
    const fileList = e.target.files as FileList | null;
    const files: File[] = fileList ? Array.from(fileList) : [];
    if (!files.length) return;
    const next: LocalAttachment[] = files.map((f) => ({
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      file: f,
      previewUrl: f.type.startsWith("image/")
        ? URL.createObjectURL(f)
        : undefined,
    }));
    setAttachments((prev) => [...prev, ...next]);
    // reset input to allow re-selecting same file

    // parse file content
    parseAndAddToChat(files[0]);

    e.currentTarget.value = "";
  };

  const removeAttachment = (id: string) => {
    setAttachments((prev) => prev.filter((a) => a.id !== id));
  };

  // 파일 파싱 및 로컬 스토리지에 저장하는 함수
  const parseAndAddToChat = async (file: File) => {
    try {
      console.log(`📁 파일 "${file.name}" 파싱을 시작합니다...`);

      // FormData 생성
      const formData = new FormData();
      formData.append("file", file);

      // localhost:8000/parse로 파일 업로드
      const response = await fetch("http://localhost:8000/parse", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(
          `파싱 요청 실패: ${response.status} ${response.statusText}`
        );
      }

      const parsedData = await response.json();

      // 파싱된 데이터를 로컬 스토리지에 저장
      const timestamp = new Date().toISOString();
      const parsedContent = {
        fileName: file.name,
        fileSize: file.size,
        fileType: file.type,
        parsedAt: timestamp,
        data: parsedData,
      };

      const storageKey = `parsed_file_${file.name}_${timestamp}`;
      localStorage.setItem(storageKey, JSON.stringify(parsedContent));

      console.log(
        `✅ 파일 "${file.name}" 파싱 완료 및 로컬 스토리지에 저장:`,
        storageKey
      );
    } catch (error) {
      console.error("파일 파싱 중 오류:", error);
    }
  };

  // 로컬 스토리지에서 파싱된 데이터들을 가져오는 함수
  const getParsedDataFromStorage = () => {
    const parsedData = [];
    const usedKey = [];
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key && key.startsWith("parsed_file_")) {
        try {
          const data = JSON.parse(localStorage.getItem(key) || "{}");
          parsedData.push(data);
        } catch (error) {
          console.error("파싱된 데이터 읽기 오류:", error);
        }

        usedKey.push(key);
      }
    }

    // 사용한 데이터 지우기
    usedKey.forEach((key) => {
      localStorage.removeItem(key);
    });

    return parsedData;
  };

  const ensureUploaded = async (): Promise<LocalAttachment[]> => {
    const needUpload = attachments.filter((a) => !a.uploaded && a.file);
    if (needUpload.length === 0) return attachments;
    setIsUploading(true);
    try {
      const form = new FormData();
      needUpload.forEach((a) => {
        if (a.file) form.append("files", a.file);
      });
      const res = await fetch(`${API_BASE}/uploads`, {
        method: "POST",
        body: form,
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || "업로드 실패");
      }
      const data = await res.json();
      const uploaded: any[] = data?.files || [];
      // merge back by order
      let idx = 0;
      const merged = attachments.map((a) => {
        if (!a.uploaded && a.file) {
          const u = uploaded[idx++];
          if (u?.url) {
            return {
              ...a,
              uploaded: {
                url: u.url as string,
                name: a.file?.name || u.filename,
                mime: a.file?.type || u.mime,
                size: a.file?.size || u.size,
                stored: u.stored,
              },
            };
          }
          return { ...a, error: "업로드 응답이 올바르지 않습니다." };
        }
        return a;
      });
      setAttachments(merged);
      return merged;
    } finally {
      setIsUploading(false);
    }
  };

  const sendMessage = async () => {
    const hasText = input.trim().length > 0;
    const hasAttachments = attachments.length > 0;
    if ((!hasText && !hasAttachments) || isSending || isProcessingRef.current)
      return; // 중복/빈 전송 방지

    isProcessingRef.current = true; // 처리 시작
    const userText = hasText
      ? input.trim()
      : hasAttachments
      ? "(첨부 전송)"
      : "";
    const userMsg: Message = { role: "user", content: userText };

    // 프로젝트가 없으면 메시지 전송을 막음
    if (!currentProject) {
      console.warn("프로젝트가 선택되지 않았습니다.");
      return;
    }

    // 사용자 메시지를 스토어에 추가
    addMessage(userMsg);

    setInput("");
    setIsSending(true);

    try {
      // 1) 아직 업로드되지 않은 첨부 업로드
      const merged = await ensureUploaded();
      const attsForChat = merged
        .filter((a) => a.uploaded?.url)
        .map((a) => ({
          url: a.uploaded!.url,
          mime: a.uploaded?.mime,
          name: a.uploaded?.name,
          size: a.uploaded?.size,
        }));
      // 초기 안내 메시지를 제외한 메시지 목록 생성
      const messagesToSend = messages.filter(
        (msg) =>
          !(
            msg.role === "assistant" &&
            msg.content ===
              "안녕하세요! 좌측 채팅창에서 질문을 보내면 우측 Code/Preview와 함께 작업을 도와드릴게요."
          )
      );

      // 로컬 스토리지에서 파싱된 데이터 가져오기
      const parsedData = getParsedDataFromStorage();

      let attachments_content = "";

      if (parsedData.length > 0) {
        attachments_content += `\n\n 첨부파일: \n\n`;

        parsedData.forEach((data) => {
          attachments_content += `\n\n - ${data.fileName}: \n\n ${data.data.parsed_data} `;
        });
      }

      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: "claude-sonnet-4-20250514",
          messages: [...messagesToSend, userMsg],
          selectedFile: selectedFilePath,
          fileContent: fileContent,
          attachments: attsForChat,
          projectName: currentProject.name,
        }),
      });

      if (!res.ok) {
        const contentType = res.headers.get("content-type") || "";
        let detail = "";
        try {
          if (contentType.includes("application/json")) {
            const body = await res.json();
            detail = body?.detail || body?.message || JSON.stringify(body);
          } else {
            const raw = await res.text();
            try {
              const parsed = JSON.parse(raw);
              detail = parsed?.detail || parsed?.message || raw;
            } catch {
              detail = raw;
            }
          }
        } catch {
          detail = "";
        }

        const status = res.status;
        const statusText = res.statusText || "";
        const friendly = (() => {
          if (status === 429)
            return "요청이 너무 많습니다. 잠시 후 다시 시도해 주세요.";
          if (status === 400) return "요청이 올바르지 않습니다.";
          if (status === 401) return "인증이 필요합니다.";
          if (status === 403) return "권한이 없습니다.";
          if (status === 404) return "요청한 리소스를 찾을 수 없습니다.";
          if (status === 408) return "요청 시간이 초과되었습니다.";
          if (status >= 500)
            return "서버 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.";
          return statusText || "요청 중 오류가 발생했습니다.";
        })();

        const shorten = (s: string, max = 160) => {
          if (!s) return "";
          const trimmed = s.toString().trim();
          return trimmed.length > max
            ? trimmed.slice(0, max - 1) + "…"
            : trimmed;
        };

        const finalMessage = `⚠️ ${friendly}${
          detail ? `\n상세: ${shorten(detail)}` : ""
        }`;
        addMessage({ role: "error", content: finalMessage });
        return;
      }

      const data = await res.json();
      const content: string =
        data?.content || "죄송합니다, 응답을 생성하지 못했습니다.";

      // 파일 업데이트가 있으면 콜백 호출
      if (data?.updatedFile && data?.updatedContent && onFileUpdate) {
        onFileUpdate(data.updatedFile, data.updatedContent);
      }

      // code_edit는 초기 짧은 응답을 표시하지 않고, 이후 폴링된 display만 보여줍니다.
      if (data?.processingType !== "code_edit") {
        addMessage({ role: "assistant", content });
      }

      // 백그라운드 코드 편집 작업만 폴링 (분석은 파일 변경이 없음)
      if (data?.processingType === "code_edit" && data?.jobId) {
        const jobId: string = data.jobId;

        const pollJob = async () => {
          try {
            for (let i = 0; i < 60; i++) {
              const jr = await fetch(`${API_BASE}/chat/jobs/${jobId}`);
              if (!jr.ok) break;
              const jd = await jr.json();
              const status: string = jd?.status || "unknown";

              if (status === "done") {
                if (jd?.display) {
                  addMessage({
                    role: "assistant",
                    content: jd.display as string,
                  });
                }
                if (onFileUpdate && jd?.updatedFile && jd?.updatedContent) {
                  onFileUpdate(
                    jd.updatedFile as string,
                    jd.updatedContent as string
                  );
                }
                return;
              }
              if (status === "error") {
                const errMsg = (
                  jd?.error ||
                  jd?.message ||
                  "작업 중 오류가 발생했습니다."
                ).toString();
                addMessage({ role: "error", content: `⚠️ ${errMsg}` });
                return;
              }
              await new Promise((r) => setTimeout(r, 1500));
            }
          } catch (e: any) {
            const m = (
              e?.message || "작업 상태 조회 중 오류가 발생했습니다."
            ).toString();
            addMessage({ role: "error", content: `⚠️ ${m}` });
          }
        };

        // 폴링 시작 (비차단)
        pollJob();
      }
    } catch (e: any) {
      console.error(e);
      const message = (() => {
        if (e?.name === "TypeError")
          return "네트워크 오류가 발생했습니다. 인터넷 연결을 확인해 주세요.";
        const m = (e?.message || "요청 중 오류가 발생했습니다.").toString();
        return m.length > 160 ? m.slice(0, 159) + "…" : m;
      })();
      addMessage({ role: "error", content: `⚠️ ${message}` });
    } finally {
      setIsSending(false);
      isProcessingRef.current = false; // 처리 완료
      // 메시지 전송 시도 후에는 항상 첨부파일 정리
      setAttachments([]);
    }
  };

  return (
    <div className="flex h-full flex-col min-h-0">
      {/* 메시지 목록 */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto overflow-x-hidden p-3 space-y-5 min-h-0 scrollbar-hide"
      >
        {messages.map((m, idx) => (
          <div
            key={idx}
            className={
              m.role === "user"
                ? "ml-auto max-w-[85%] rounded-lg bg-indigo-600/90 text-white px-3 py-2 break-words whitespace-pre-wrap"
                : m.role === "error"
                ? "mr-auto max-w-[85%] rounded-lg bg-red-500/10 text-red-200 px-3 py-2 border border-red-400/30 break-words whitespace-pre-wrap"
                : "mr-auto max-w-[85%] rounded-lg bg-white/5 text-slate-200 px-3 py-2 border border-white/10 break-words whitespace-pre-wrap"
            }
          >
            {m.content}
          </div>
        ))}

        {isSending && (
          <div className="mr-auto inline-flex items-center gap-2 rounded-lg bg-white/5 text-slate-200 px-3 py-2 border border-white/10 mb-5 max-w-[85%]">
            <span className="w-3 h-3 rounded-full bg-cyan-400 animate-pulse" />
            생각 중...
          </div>
        )}
      </div>

      {/* 에러 말풍선으로 대체됨 */}

      {/* 첨부 미리보기 / 관리 바 */}
      {attachments.length > 0 && (
        <div className="px-3 py-2 border-t border-white/10 bg-white/5">
          <div className="flex flex-wrap gap-2">
            {attachments.map((a) => (
              <div
                key={a.id}
                className="relative flex items-center gap-2 rounded-md border border-white/10 bg-[#0b0f1a]/60 px-2 py-1"
              >
                {a.previewUrl ? (
                  <img
                    src={a.previewUrl}
                    alt={a.uploaded?.name || a.file?.name || "attachment"}
                    className="w-12 h-12 object-cover rounded"
                  />
                ) : (
                  <File size={16} />
                )}
                <div className="text-xs text-slate-300 max-w-[200px] truncate">
                  {a.uploaded?.name || a.file?.name}
                </div>
                <button
                  onClick={() => removeAttachment(a.id)}
                  className="ml-1 p-1 rounded hover:bg-white/10"
                  title="첨부 제거"
                  aria-label="Remove attachment"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* 선택된 파일 표시 */}
      {selectedFilePath && (
        <div className="px-3 py-2 text-xs text-cyan-200 bg-cyan-500/10 border-t border-cyan-400/30">
          <div className="flex items-center justify-between">
            <span>📁 선택된 파일: {selectedFilePath}</span>
            {onClearSelectedFile && (
              <button
                onClick={onClearSelectedFile}
                className="ml-2 p-1 rounded-md hover:bg-cyan-400/20 transition-colors"
                title="파일 선택 해제"
                aria-label="Clear selected file"
              >
                <X size={14} />
              </button>
            )}
          </div>
        </div>
      )}

      {/* 입력/액션 바 */}
      <div className="p-2 border-t border-white/10 bg-white/5 space-y-2">
        <div className="px-1">
          <div className="flex items-center gap-2 rounded-xl border border-white/10 bg-[#0b0f1a]/60 focus-within:border-cyan-400/40 focus-within:ring-2 focus-within:ring-cyan-400/20 px-3 py-2">
            <button
              type="button"
              onClick={onPickFiles}
              disabled={isSending || isProcessingRef.current || isUploading}
              className="inline-flex items-center justify-center h-9 w-9 rounded-lg text-white hover:bg-white/10 disabled:opacity-60"
              title="파일 첨부"
              aria-label="Attach files"
            >
              <Paperclip size={16} />
            </button>
            <textarea
              ref={inputRef}
              className="flex-1 bg-transparent text-white placeholder:text-slate-400 border-0 outline-none resize-none text-sm min-h-[44px] max-h-40 py-2.5"
              rows={1}
              placeholder="메시지를 입력하세요"
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                autoSize();
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  sendMessage();
                }
              }}
            />
            <button
              disabled={
                isSending ||
                (input.trim().length === 0 && attachments.length === 0) ||
                isProcessingRef.current ||
                isUploading
              }
              className="inline-flex items-center justify-center h-9 w-9 rounded-lg text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-60"
              onClick={sendMessage}
              title="메시지 전송"
              aria-label="Send message"
            >
              <Send size={16} />
            </button>
          </div>
          <div className="text-[11px] text-slate-400/80 mt-1 px-1">
            Enter 전송 · Shift+Enter 줄바꿈
            {isUploading ? " · 파일 업로드 중..." : ""}
          </div>
          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            onChange={onFilesSelected}
            accept="image/*,application/pdf,text/plain,text/markdown,.md,.markdown,application/zip,application/json"
          />
        </div>
      </div>
    </div>
  );
};
