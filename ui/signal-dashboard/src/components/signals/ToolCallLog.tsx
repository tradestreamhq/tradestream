import type { ToolCallEvent, ToolResultEvent } from "@/api/types";

interface ToolCallLogProps {
  events: (ToolCallEvent | ToolResultEvent)[];
}

export function ToolCallLog({ events }: ToolCallLogProps) {
  if (events.length === 0) return null;

  return (
    <section aria-labelledby="tool-calls-heading">
      <h4
        id="tool-calls-heading"
        className="mb-3 text-xs font-semibold uppercase tracking-wider text-slate-500"
      >
        Tool Calls
      </h4>
      <div className="space-y-2 rounded-lg bg-slate-800/50 p-3 font-mono text-xs">
        {events.map((event, i) => {
          if (event.event_type === "tool_call") {
            return (
              <div key={i} className="flex items-start gap-2">
                <span className="shrink-0 rounded bg-blue-500/20 px-1.5 py-0.5 text-blue-400">
                  call
                </span>
                <span className="text-slate-300">
                  {event.tool_name}({event.arguments})
                </span>
                <span className="ml-auto shrink-0 text-slate-500">
                  {event.latency_ms}ms
                </span>
              </div>
            );
          }
          return (
            <div key={i} className="flex items-start gap-2 pl-4">
              <span className="shrink-0 text-slate-500">&rarr;</span>
              <span className="text-slate-400">{event.result_summary}</span>
            </div>
          );
        })}
      </div>
    </section>
  );
}
