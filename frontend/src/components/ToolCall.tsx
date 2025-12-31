import React from "react";
import { ChevronDown, ChevronRight, Terminal } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

import { cn } from "@/lib/utils";
import { formatArgsPreview, isBashTool, type ToolResult } from "@/lib/format";

export type ToolCallProps = {
  toolName: string;
  argsRaw: string;
  result?: ToolResult;
  className?: string;
};

export function ToolCall({ toolName, argsRaw, result, className }: ToolCallProps) {
  const [expanded, setExpanded] = React.useState(false);
  const preview = formatArgsPreview(toolName, argsRaw);
  const label = isBashTool(toolName)
    ? preview
    : argsRaw
      ? `${toolName}: ${preview}`
      : toolName;

  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className={cn(
        "min-w-0 max-w-full rounded-2xl border-l-4 border-emerald-500/50 bg-emerald-50/50 px-4 py-3 shadow-sm hover:shadow-md transition-shadow",
        className
      )}
    >
      <button
        type="button"
        onClick={() => setExpanded((current) => !current)}
        className="flex w-full items-center justify-between gap-3 text-left group"
      >
        <div className="flex min-w-0 items-center gap-2 text-sm font-semibold text-emerald-800">
          <div className="flex h-6 w-6 items-center justify-center rounded-lg bg-emerald-200/50 text-emerald-700 group-hover:bg-emerald-200">
             {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
          </div>
          <Terminal size={14} className="text-emerald-600/70" />
          <span className="truncate font-mono text-xs">{label}</span>
        </div>
        <span className="text-[10px] font-bold uppercase tracking-widest text-emerald-700/50">
          Run
        </span>
      </button>

      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="mt-3 space-y-2">
              <div className="rounded-xl border border-emerald-200/50 bg-white/80 p-3 text-xs text-emerald-900 shadow-inner">
                <div className="mb-2 flex items-center justify-between text-[10px] font-bold uppercase tracking-widest text-emerald-700/70">
                  <span>Output</span>
                  {result && (
                    <span className={cn(result.exitCode === 0 ? "text-emerald-600" : "text-rose-600")}>
                      exit {result.exitCode}
                    </span>
                  )}
                </div>
                <pre className="whitespace-pre-wrap break-all font-mono text-[11px] leading-relaxed text-emerald-950">
                  {result
                    ? result.output
                      ? result.output
                      : "(no output)"
                    : "Waiting for output..."}
                </pre>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
