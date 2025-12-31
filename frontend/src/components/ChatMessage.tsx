import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { motion, AnimatePresence } from "framer-motion";
import { Copy, Check } from "lucide-react";

import { cn } from "@/lib/utils";

export type ChatRole =
  | "user"
  | "assistant"
  | "system"
  | "thinking"
  | "developer"
  | "tool"
  | string;

const ROLE_LABELS: Record<string, string> = {
  user: "You",
  assistant: "Binsmith",
  thinking: "Binsmith (thinking)",
  system: "System",
  developer: "System",
  tool: "Tool"
};

const ROLE_STYLES: Record<string, string> = {
  user: "border-l-0 border-r-4 border-orange-400/70 bg-orange-50/80",
  assistant: "border-teal-500/70 bg-teal-50/70",
  thinking: "border-slate-400/70 bg-slate-50/80",
  system: "border-slate-400/70 bg-slate-100/80",
  developer: "border-slate-400/70 bg-slate-100/80",
  tool: "border-emerald-500/70 bg-emerald-50/70"
};

const ROLE_LABEL_STYLES: Record<string, string> = {
  user: "text-orange-700",
  assistant: "text-teal-800",
  thinking: "text-slate-500",
  system: "text-slate-600",
  developer: "text-slate-600",
  tool: "text-emerald-700"
};

export type ChatMessageProps = {
  role: ChatRole;
  content: string;
  className?: string;
};

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = React.useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      className="absolute right-2 top-2 rounded-lg bg-white/10 p-1.5 text-white/50 transition-colors hover:bg-white/20 hover:text-white"
    >
      {copied ? <Check size={14} /> : <Copy size={14} />}
    </button>
  );
}

export function ChatMessage({ role, content, className }: ChatMessageProps) {
  const label = ROLE_LABELS[role] ?? role;
  const shellClass = ROLE_STYLES[role] ?? "border-l-4 shadow-sm";
  const labelClass = ROLE_LABEL_STYLES[role] ?? "text-ink-600";
  
  const bubbleStyles = cn(
    "flex flex-col min-w-0 max-w-full overflow-hidden rounded-2xl px-4 py-3 transition-shadow duration-300 hover:shadow-md",
    ROLE_STYLES[role] ?? "border-ink-200 bg-white/80",
    shellClass,
    className
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: 10, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className={bubbleStyles}
    >
      <div className="flex items-center justify-between mb-1">
        <div className={cn("text-[10px] font-bold uppercase tracking-[0.2em]", labelClass)}>
          {label}
        </div>
      </div>
      {role === "assistant" ? (
        <div className="min-w-0 flex-1">
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={{
              pre: ({ children, ...props }) => (
                <div className="relative group">
                  <pre {...props} className="overflow-x-auto rounded-xl p-4 my-2 bg-ink-900/5 dark:bg-ink-900/10">
                    {children}
                  </pre>
                  {/* Note: In a real app we would extract the text from children here */}
                </div>
              ),
            }}
            className="prose prose-sm max-w-none break-words text-ink-800 leading-relaxed prose-pre:bg-ink-900/5 prose-pre:border prose-pre:border-ink-200/50"
          >
            {content}
          </ReactMarkdown>
        </div>
      ) : (
        <p
          className={cn(
            "whitespace-pre-wrap break-all text-sm leading-relaxed text-ink-800",
            role === "thinking" && "italic text-slate-500",
            (role === "system" || role === "developer") && "text-slate-500"
          )}
        >
          {content}
        </p>
      )}
    </motion.div>
  );
}
