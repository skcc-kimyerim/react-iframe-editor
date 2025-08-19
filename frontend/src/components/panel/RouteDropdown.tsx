import React, { useEffect, useRef, useState } from "react";
import { ChevronDown, Check } from "lucide-react";

export type RouteDropdownProps = {
  label: string;
  value: string;
  options: string[];
  onChange: (v: string) => void;
};

export const RouteDropdown: React.FC<RouteDropdownProps> = ({
  label,
  value,
  options,
  onChange,
}) => {
  const [open, setOpen] = useState(false);
  const [highlightIndex, setHighlightIndex] = useState<number>(-1);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const listRef = useRef<HTMLDivElement | null>(null);

  const currentIndex = Math.max(
    0,
    options.findIndex((r) => r === value)
  );

  useEffect(() => {
    setHighlightIndex(currentIndex);
  }, [open, currentIndex]);

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (!rootRef.current) return;
      if (!rootRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (!open) return;
    const container = listRef.current;
    if (!container) return;
    const active = container.querySelector<HTMLElement>(
      `[data-index='${highlightIndex}']`
    );
    if (active) {
      active.scrollIntoView({ block: "nearest" });
    }
  }, [open, highlightIndex]);

  const handleKey = (e: React.KeyboardEvent) => {
    if (
      !open &&
      (e.key === "ArrowDown" || e.key === "Enter" || e.key === "Space")
    ) {
      e.preventDefault();
      setOpen(true);
      return;
    }
    if (!open) return;
    if (e.key === "Escape") {
      e.preventDefault();
      setOpen(false);
      return;
    }
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setHighlightIndex((i) =>
        Math.min(options.length - 1, (i < 0 ? currentIndex : i) + 1)
      );
      return;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      setHighlightIndex((i) => Math.max(0, (i < 0 ? currentIndex : i) - 1));
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      const idx = highlightIndex < 0 ? currentIndex : highlightIndex;
      const next = options[idx] ?? value;
      onChange(next);
      setOpen(false);
    }
  };

  return (
    <section
      ref={rootRef}
      className="relative flex items-center gap-2 min-w-[220px]"
    >
      <span className="text-xs opacity-80">{label}</span>
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        onKeyDown={handleKey}
        className="flex-1 inline-flex items-center justify-between bg-[#0f121f] text-white border border-white/10 rounded px-2 py-1 text-xs hover:bg-white/10 focus:outline-none focus:border-cyan-400/60 focus:ring-2 focus:ring-cyan-400/20"
        title="Select route"
      >
        <span className="truncate">{value || "/"}</span>
        <ChevronDown
          className={`h-4 w-4 transition-transform ${
            open ? "rotate-180" : "rotate-0"
          }`}
        />
      </button>

      {open && (
        <div
          ref={listRef}
          role="listbox"
          tabIndex={-1}
          className="absolute right-0 top-full mt-2 z-50 w-48 max-h-64 overflow-auto rounded-md border border-white/10 bg-[#0b0f1a] shadow-xl ring-1 ring-black/30 backdrop-blur"
        >
          <div className="py-1">
            {options.map((r, idx) => {
              const isSelected = r === value;
              const isActive = idx === highlightIndex;
              return (
                <button
                  key={r}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  data-index={idx}
                  className={`w-full flex items-center gap-2 px-3 py-1.5 text-left text-xs ${
                    isActive ? "bg-white/10" : "hover:bg-white/10"
                  } ${isSelected ? "text-cyan-300" : "text-slate-200"}`}
                  onMouseEnter={() => setHighlightIndex(idx)}
                  onClick={() => {
                    onChange(r);
                    setOpen(false);
                  }}
                >
                  <Check
                    className={`h-4 w-4 ${
                      isSelected ? "opacity-100" : "opacity-0"
                    }`}
                  />
                  <span className="truncate">{r}</span>
                </button>
              );
            })}
          </div>
        </div>
      )}
    </section>
  );
};
