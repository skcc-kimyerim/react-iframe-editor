import React, { useEffect, useRef, useState } from "react";
import { Send, X } from "lucide-react";

type Role = "user" | "assistant" | "system" | "error";
type Message = { role: Role; content: string };

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
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        "안녕하세요! 좌측 채팅창에서 질문을 보내면 우측 Code/Preview와 함께 작업을 도와드릴게요.",
    },
  ]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const isProcessingRef = useRef<boolean>(false); // API 호출 중복 방지

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

  const sendMessage = async () => {
    if (!input.trim() || isSending || isProcessingRef.current) return; // 중복 호출 방지

    isProcessingRef.current = true; // 처리 시작
    const userMsg: Message = { role: "user", content: input.trim() };

    // 첫 번째 메시지를 보낼 때 초기 안내 메시지 제거
    setMessages((prev) => {
      // 초기 안내 메시지가 있다면 제거하고 사용자 메시지만 추가
      if (
        prev.length === 1 &&
        prev[0].role === "assistant" &&
        prev[0].content ===
          "안녕하세요! 좌측 채팅창에서 질문을 보내면 우측 Code/Preview와 함께 작업을 도와드릴게요."
      ) {
        return [userMsg];
      }
      return [...prev, userMsg];
    });

    setInput("");
    setIsSending(true);

    try {
      // 초기 안내 메시지를 제외한 메시지 목록 생성
      const messagesToSend = messages.filter(
        (msg) =>
          !(
            msg.role === "assistant" &&
            msg.content ===
              "안녕하세요! 좌측 채팅창에서 질문을 보내면 우측 Code/Preview와 함께 작업을 도와드릴게요."
          )
      );

      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: "qwen/qwen3-coder",
          messages: [...messagesToSend, userMsg],
          selectedFile: selectedFilePath,
          fileContent: fileContent,
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
        setMessages((prev) => [
          ...prev,
          { role: "error", content: finalMessage },
        ]);
        return;
      }

      const data = await res.json();
      const content: string =
        data?.content || "죄송해요, 응답을 생성하지 못했습니다.";

      // 파일 업데이트가 있으면 콜백 호출
      if (data?.updatedFile && data?.updatedContent && onFileUpdate) {
        onFileUpdate(data.updatedFile, data.updatedContent);
      }

      // code_edit는 초기 짧은 응답을 표시하지 않고, 이후 폴링된 display만 보여줍니다.
      if (data?.processingType !== "code_edit") {
        setMessages((prev) => [...prev, { role: "assistant", content }]);
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
                  setMessages((prev) => [
                    ...prev,
                    { role: "assistant", content: jd.display as string },
                  ]);
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
                setMessages((prev) => [
                  ...prev,
                  { role: "error", content: `⚠️ ${errMsg}` },
                ]);
                return;
              }
              await new Promise((r) => setTimeout(r, 1500));
            }
          } catch (e: any) {
            const m = (
              e?.message || "작업 상태 조회 중 오류가 발생했습니다."
            ).toString();
            setMessages((prev) => [
              ...prev,
              { role: "error", content: `⚠️ ${m}` },
            ]);
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
      setMessages((prev) => [
        ...prev,
        { role: "error", content: `⚠️ ${message}` },
      ]);
    } finally {
      setIsSending(false);
      isProcessingRef.current = false; // 처리 완료
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
                input.trim().length === 0 ||
                isProcessingRef.current
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
          </div>
        </div>
      </div>
    </div>
  );
};
