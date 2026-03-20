import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";
import { ToolCallLog } from "../ToolCallLog";
import { createMockEvent } from "./testHelpers";

describe("ToolCallLog", () => {
  it("renders nothing when no tool call events", () => {
    const { container } = render(<ToolCallLog events={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders tool calls from events", () => {
    const events = [
      createMockEvent({
        event_type: "tool_call",
        tool_calls: [
          { name: "get_top_strategies", args: { symbol: "ETH/USD" } },
        ],
      }),
    ];
    render(<ToolCallLog events={events} />);
    expect(screen.getByText("get_top_strategies")).toBeInTheDocument();
    expect(screen.getByText("Tool Calls")).toBeInTheDocument();
  });
});
