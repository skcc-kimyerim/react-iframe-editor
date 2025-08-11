import React, { useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";

type Role = "user" | "assistant" | "system";
type Message = { role: Role; content: string };

const API_BASE = "http://localhost:3001/api";

interface ChatProps {
  selectedFilePath?: string;
  fileContent?: string;
  onFileUpdate?: (filePath: string, content: string) => void;
}

export const Chat: React.FC<ChatProps> = ({
  selectedFilePath,
  fileContent,
  onFileUpdate,
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
  const [error, setError] = useState<string>("");
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

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
    if (!input.trim()) return;
    const userMsg: Message = { role: "user", content: input.trim() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsSending(true);
    setError("");

    try {
      const res = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: "qwen/qwen3-coder:free",
          messages: [...messages, userMsg],
          selectedFile: selectedFilePath,
          fileContent: fileContent,
        }),
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Request failed: ${res.status}`);
      }

      const data = await res.json();
      const content: string =
        data?.content || "죄송해요, 응답을 생성하지 못했습니다.";

      // 파일 업데이트가 있으면 콜백 호출
      if (data?.updatedFile && data?.updatedContent && onFileUpdate) {
        onFileUpdate(data.updatedFile, data.updatedContent);
      }

      setMessages((prev) => [...prev, { role: "assistant", content }]);
    } catch (e: any) {
      console.error(e);
      setError(e?.message || "요청 중 오류가 발생했습니다.");
    } finally {
      setIsSending(false);
    }
  };

  return (
    <div className="flex h-full flex-col min-h-0">
      {/* 서버 프록시 모드 - 별도 키 입력 불필요 */}

      {/* 메시지 목록 */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto overflow-x-hidden p-3 space-y-5 min-h-0"
      >
        {messages.map((m, idx) => (
          <div
            key={idx}
            className={
              m.role === "user"
                ? "ml-auto max-w-[85%] rounded-lg bg-indigo-600/90 text-white px-3 py-2 break-words whitespace-pre-wrap"
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

      {/* 에러 */}
      {error && (
        <div className="px-3 py-2 text-xs text-red-200 bg-red-500/10 border-t border-red-400/30">
          {error}
        </div>
      )}

      {/* 선택된 파일 표시 */}
      {selectedFilePath && (
        <div className="px-3 py-2 text-xs text-cyan-200 bg-cyan-500/10 border-t border-cyan-400/30">
          📁 선택된 파일: {selectedFilePath}
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
              disabled={isSending || input.trim().length === 0}
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
