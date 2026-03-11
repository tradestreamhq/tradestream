import { render, screen } from "@testing-library/react";
import React from "react";
import { describe, expect, it } from "vitest";
import { StatCard } from "../StatCard";

describe("StatCard", () => {
  it("renders label and value", () => {
    render(<StatCard label="Decisions" value={42} />);
    expect(screen.getByText("Decisions")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
  });

  it("applies color class", () => {
    render(<StatCard label="Active" value={3} color="green" />);
    const valueEl = screen.getByText("3");
    expect(valueEl.className).toContain("green");
  });

  it("has accessible role and label", () => {
    render(<StatCard label="Signals" value={15} />);
    const status = screen.getByRole("status");
    expect(status).toHaveAttribute("aria-label", "Signals: 15");
  });
});
