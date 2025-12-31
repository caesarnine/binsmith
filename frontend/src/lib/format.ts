const COMMAND_REGEX = /["']command["']\s*:\s*["']([^"']+)["']/;

export function isBashTool(toolName: string) {
  return toolName === "bash" || toolName.endsWith(":bash");
}

export function extractCommand(rawArgs: string) {
  try {
    const data = JSON.parse(rawArgs);
    if (data && typeof data === "object" && "command" in data) {
      return String((data as { command: unknown }).command ?? "");
    }
  } catch {
    // ignore
  }

  const match = COMMAND_REGEX.exec(rawArgs);
  return match ? match[1] : null;
}

export function looksLikeCompleteJson(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return false;
  if (!(
    (trimmed.startsWith("{") && trimmed.endsWith("}")) ||
    (trimmed.startsWith("[") && trimmed.endsWith("]"))
  )) {
    return false;
  }
  try {
    JSON.parse(trimmed);
    return true;
  } catch {
    return false;
  }
}

export function appendToolArgs(existing: string, delta: string) {
  if (!delta) return existing;
  if (looksLikeCompleteJson(delta)) {
    return delta;
  }
  return existing + delta;
}

export function formatArgsPreview(toolName: string, rawArgs: string) {
  if (!rawArgs) {
    return toolName;
  }

  if (isBashTool(toolName)) {
    const command = extractCommand(rawArgs);
    if (command) {
      return `$ ${command.replace(/\n/g, " ").slice(0, 60)}`;
    }

    const partialMatch = /["']command["']\s*:\s*["']([^"']*)/.exec(rawArgs);
    if (partialMatch) {
      return `$ ${partialMatch[1].replace(/\n/g, " ").slice(0, 60)}`;
    }

    return `$ ${rawArgs.slice(0, 60)}`;
  }

  try {
    const parsed = JSON.parse(rawArgs);
    if (parsed && typeof parsed === "object") {
      if ("command" in parsed) {
        return `$ ${String((parsed as { command: unknown }).command ?? "").slice(0, 60)}`;
      }
      return JSON.stringify(parsed).slice(0, 60);
    }
  } catch {
    // ignore
  }

  return rawArgs.slice(0, 60);
}

export function truncateOutput(output: string, limit = 4000) {
  if (output.length <= limit) {
    return output;
  }
  return `${output.slice(0, limit)}\n... (truncated, ${output.length - limit} chars)`;
}

export type ToolResult = {
  output: string;
  exitCode: number;
  timedOut: boolean;
};

export function parseToolResult(content: string): ToolResult {
  let data: unknown = content;

  if (typeof content === "string") {
    const stripped = content.trim();
    if (stripped.startsWith("{") || stripped.startsWith("[")) {
      try {
        data = JSON.parse(stripped);
      } catch {
        data = content;
      }
    }
  }

  if (data && typeof data === "object") {
    const maybeContent = (data as { content?: unknown }).content;
    if (maybeContent !== undefined) {
      data = maybeContent;
    }
    const maybeData = (data as { data?: unknown }).data;
    if (maybeData !== undefined) {
      data = maybeData;
    }
  }

  let output = "";
  let exitCode = 0;
  let timedOut = false;

  if (data && typeof data === "object") {
    const typed = data as {
      stdout?: string | null;
      stderr?: string | null;
      exit_code?: number;
      exitCode?: number;
      timed_out?: boolean;
      timedOut?: boolean;
    };

    const stdout = typed.stdout ?? "";
    const stderr = typed.stderr ?? "";
    if (stdout || stderr) {
      output = stdout && stderr ? `${stdout}\n${stderr}` : stdout || stderr;
    }
    exitCode = typed.exit_code ?? typed.exitCode ?? 0;
    timedOut = Boolean(typed.timed_out ?? typed.timedOut ?? false);
  } else if (data != null) {
    output = String(data);
  }

  output = truncateOutput(output);
  return { output, exitCode, timedOut };
}
