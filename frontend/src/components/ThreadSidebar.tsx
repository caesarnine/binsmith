import React from "react";
import { Plus, RefreshCcw, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

export type ThreadSidebarProps = {
  threads: string[];
  currentThread: string | null;
  onSelect: (threadId: string) => void;
  onCreate: () => void;
  onRefresh: () => void;
  isLoading?: boolean;
  sessionId?: string | null;
  serverUrl?: string;
  model?: string | null;
  defaultModel?: string | null;
  models?: string[] | null;
  isLoadingModels?: boolean;
  onLoadModels?: () => void;
  onSelectModel?: (model: string | null) => void;
  onClose?: () => void;
};

export function ThreadSidebar({
  threads,
  currentThread,
  onSelect,
  onCreate,
  onRefresh,
  isLoading,
  sessionId,
  serverUrl,
  model,
  defaultModel,
  models,
  isLoadingModels,
  onLoadModels,
  onSelectModel,
  onClose
}: ThreadSidebarProps) {
  const [isModelOpen, setIsModelOpen] = React.useState(false);
  const [modelQuery, setModelQuery] = React.useState("");

  React.useEffect(() => {
    if (isModelOpen && onLoadModels) {
      onLoadModels();
    }
  }, [isModelOpen, onLoadModels]);

  const displayModel = model || defaultModel || "Default";
  const normalizedQuery = modelQuery.trim().toLowerCase();
  const allModels = models ?? [];
  const filteredModels = normalizedQuery
    ? allModels.filter((item) => item.toLowerCase().includes(normalizedQuery))
    : allModels;
  const visibleModels = normalizedQuery ? filteredModels : filteredModels.slice(0, 50);
  return (
    <aside className="flex h-full flex-col border-ink-200/70 bg-glass shadow-soft md:rounded-3xl md:border overflow-hidden">
      <div className="space-y-4 px-5 pb-4 pt-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="text-xs font-semibold uppercase tracking-[0.3em] text-ink-500">
              Binsmith
            </div>
            <div className="text-2xl font-display text-ink-900">Threads</div>
          </div>
          <div className="flex items-center gap-2">
            <Button size="icon" variant="ghost" onClick={onRefresh}>
              <RefreshCcw size={16} />
            </Button>
            {onClose ? (
              <Button size="icon" variant="ghost" onClick={onClose}>
                <X size={16} />
              </Button>
            ) : null}
          </div>
        </div>
        <Button className="w-full rounded-2xl bg-ink-900 py-6 text-white hover:bg-ink-800" onClick={onCreate}>
          <Plus size={16} className="mr-2" />
          New Thread
        </Button>
        <div className="rounded-2xl border border-ink-200/70 bg-white/60 p-3">
          <button
            type="button"
            onClick={() => setIsModelOpen((open) => !open)}
            className="flex w-full items-center justify-between text-left text-xs font-semibold uppercase tracking-widest text-ink-500"
          >
            <span>Model</span>
            <span className="max-w-[140px] truncate text-ink-900 normal-case" title={displayModel}>
              {displayModel}
            </span>
          </button>
          {isModelOpen ? (
            <div className="mt-3 space-y-3">
              <Input
                value={modelQuery}
                onChange={(event) => setModelQuery(event.target.value)}
                placeholder="Search models"
                className="h-9 text-xs"
              />
              <div className="max-h-56 overflow-hidden rounded-xl border border-ink-200/60 bg-white/70">
                <ScrollArea className="h-56 px-2 py-2">
                  {isLoadingModels ? (
                    <div className="p-2 text-xs text-ink-500">Loading models...</div>
                  ) : visibleModels.length ? (
                    visibleModels.map((item) => (
                      <button
                        key={item}
                        type="button"
                        onClick={() => {
                          onSelectModel?.(item);
                          setIsModelOpen(false);
                          setModelQuery("");
                        }}
                        className={cn(
                          "w-full rounded-lg px-3 py-2 text-left text-xs transition-colors",
                          item === displayModel
                            ? "bg-teal-100 text-teal-900"
                            : "text-ink-600 hover:bg-ink-100/70"
                        )}
                      >
                        {item}
                      </button>
                    ))
                  ) : (
                    <div className="p-2 text-xs text-ink-500">No matches.</div>
                  )}
                </ScrollArea>
              </div>
              {!normalizedQuery && allModels.length > visibleModels.length ? (
                <div className="text-[11px] text-ink-400">
                  Showing {visibleModels.length} of {allModels.length}. Type to search.
                </div>
              ) : null}
              {defaultModel && displayModel !== defaultModel ? (
                <Button
                  size="sm"
                  variant="outline"
                  className="w-full text-xs"
                  onClick={() => {
                    onSelectModel?.(null);
                    setIsModelOpen(false);
                    setModelQuery("");
                  }}
                >
                  Reset to default
                </Button>
              ) : null}
            </div>
          ) : null}
        </div>
      </div>

      <Separator />

      <ScrollArea className="flex-1 px-3 py-4">
        <div className="space-y-2">
          {threads.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-ink-200 bg-white/40 p-4 text-sm text-ink-500">
              No threads yet. Create one to get started.
            </div>
          ) : (
            threads.map((thread) => (
              <button
                key={thread}
                onClick={() => onSelect(thread)}
                className={cn(
                  "flex w-full items-center justify-between rounded-2xl border px-4 py-3 text-left text-sm transition-all duration-200",
                  thread === currentThread
                    ? "border-teal-500/50 bg-teal-50 shadow-sm text-teal-900"
                    : "border-transparent bg-white/40 text-ink-600 hover:bg-white/70 hover:text-ink-900"
                )}
              >
                <span className="truncate font-semibold">{thread}</span>
                {thread === currentThread ? (
                  <Badge variant="accent" className="text-[10px] uppercase">
                    Active
                  </Badge>
                ) : null}
              </button>
            ))
          )}
        </div>
      </ScrollArea>

      <Separator />

      <div className="space-y-2 px-5 pb-5 pt-4 text-xs text-ink-500">
        <div className="flex flex-wrap items-center gap-2">
          <span className="uppercase tracking-widest">Session</span>
          <Badge variant="default" className="text-[10px]">
            {sessionId ? `${sessionId.slice(0, 6)}…${sessionId.slice(-4)}` : "-"}
          </Badge>
        </div>
        <div className="text-[11px] text-ink-400">
          {serverUrl ?? ""}
        </div>
        {isLoading ? (
          <div className="text-[11px] text-ink-500">Loading threads…</div>
        ) : null}
      </div>
    </aside>
  );
}
