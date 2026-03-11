import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";
import { ToolCallLog } from "../ToolCallLog";

describe("ToolCallLog", () => {
  it("renders tool calls", () => {
    const toolCalls = [
      { name: "get_candles", args: { symbol: "BTC" } },
      { name: "get_signals", args: {} },
    ];
    render(<ToolCallLog toolCalls={toolCalls} />);
    expect(screen.getByText("get_candles")).toBeInTheDocument();
    expect(screen.getByText("get_signals")).toBeInTheDocument();
    expect(screen.getByText("Tool Calls (2)")).toBeInTheDocument();
  });

  it("renders nothing for empty array", () => {
    const { container } = render(<ToolCallLog toolCalls={[]} />);
    expect(container.firstChild).toBeNull();
  });
});
