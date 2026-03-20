import { render, screen } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { ToolCallLog } from "../ToolCallLog";
import type { ToolCallEvent, ToolResultEvent } from "@/api/types";

describe("ToolCallLog", () => {
  it("renders tool calls with latency", () => {
    const events: (ToolCallEvent | ToolResultEvent)[] = [
      { event_type: "tool_call", tool_name: "get_top_strategies", arguments: 'symbol="ETH/USD"', latency_ms: 45 },
      { event_type: "tool_result", tool_name: "get_top_strategies", result_summary: "RSI_REVERSAL (0.89), MACD_CROSS (0.85)" },
    ];

    render(<ToolCallLog events={events} />);

    expect(screen.getByText("Tool Calls")).toBeInTheDocument();
    expect(screen.getByText(/get_top_strategies/)).toBeInTheDocument();
    expect(screen.getByText("45ms")).toBeInTheDocument();
    expect(screen.getByText("RSI_REVERSAL (0.89), MACD_CROSS (0.85)")).toBeInTheDocument();
  });

  it("returns null for empty events", () => {
    const { container } = render(<ToolCallLog events={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("shows call badge", () => {
    const events: (ToolCallEvent | ToolResultEvent)[] = [
      { event_type: "tool_call", tool_name: "fetch", arguments: '"/price"', latency_ms: 20 },
    ];

    render(<ToolCallLog events={events} />);
    expect(screen.getByText("call")).toBeInTheDocument();
  });
});
