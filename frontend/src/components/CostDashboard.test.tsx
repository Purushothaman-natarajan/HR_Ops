import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { CostDashboard } from "./CostDashboard";
import { api } from "../api/client";

// Mock the API client
vi.mock("../api/client", () => ({
  api: {
    trace: {
      runs: vi.fn(),
    },
  },
}));

describe("CostDashboard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Silence console.warn for the error test
    vi.spyOn(console, "warn").mockImplementation(() => {});
  });

  it("renders loading state initially", async () => {
    // Return an unresolved promise to keep it in loading state
    vi.mocked(api.trace.runs).mockReturnValue(new Promise(() => {}));

    render(<CostDashboard />);

    expect(screen.getByText("Loading cost data...")).toBeInTheDocument();
  });

  it("renders error state when API fails", async () => {
    // Return a rejected promise
    vi.mocked(api.trace.runs).mockRejectedValue(new Error("Network Error"));

    render(<CostDashboard />);

    // Wait for the error state to render
    await waitFor(() => {
      expect(screen.getByText("Could not load cost data. Backend may be unavailable.")).toBeInTheDocument();
    });
  });

  it("renders empty state when API returns no data", async () => {
    // Return an empty runs array
    vi.mocked(api.trace.runs).mockResolvedValue({
      data: { runs: [] },
      status: 200,
      statusText: "OK",
      headers: new Headers(),
      config: {} as any
    } as any);

    render(<CostDashboard />);

    await waitFor(() => {
      expect(screen.getByText("No cost data available yet. Submit some queries first.")).toBeInTheDocument();
    });
  });

  it("calculates and renders aggregated cost data correctly", async () => {
    // Mock data with multiple agents and some edge cases (missing cost, unknown agent)
    vi.mocked(api.trace.runs).mockResolvedValue({
      data: {
        runs: [
          {
            trace_events: [
              { agent_role: "researcher", cost_usd: 0.05 },
              { agent_role: "writer", cost_usd: 0.02 },
            ],
          },
          {
            trace_events: [
              { agent_role: "researcher", cost_usd: 0.03 },
              // Edge case: missing cost_usd
              { agent_role: "reviewer" },
              // Edge case: missing agent_role
              { cost_usd: 0.01 },
            ],
          },
        ],
      },
    } as any);

    render(<CostDashboard />);

    // Wait for loading to finish
    await waitFor(() => {
      expect(screen.queryByText("Loading cost data...")).not.toBeInTheDocument();
    });

    // Check Total Cost (0.05 + 0.02 + 0.03 + 0 + 0.01 = 0.11)
    expect(screen.getByText("$0.11000")).toBeInTheDocument();

    // Check Total LLM Calls (5 events)
    expect(screen.getByText("5")).toBeInTheDocument();

    // Check Avg Cost/Call (0.11 / 5 = 0.022)
    expect(screen.getByText("$0.022000")).toBeInTheDocument();

    // Check Agent breakdown in the table (should be sorted by cost)
    const rows = screen.getAllByRole("row");
    // header is row[0]

    // 1st row: researcher (cost: 0.08, calls: 2)
    expect(rows[1]).toHaveTextContent("researcher");
    expect(rows[1]).toHaveTextContent("2");
    expect(rows[1]).toHaveTextContent("$0.08000");

    // 2nd row: writer (cost: 0.02, calls: 1)
    expect(rows[2]).toHaveTextContent("writer");
    expect(rows[2]).toHaveTextContent("1");
    expect(rows[2]).toHaveTextContent("$0.02000");

    // 3rd row: unknown (cost: 0.01, calls: 1)
    expect(rows[3]).toHaveTextContent("unknown");
    expect(rows[3]).toHaveTextContent("1");
    expect(rows[3]).toHaveTextContent("$0.01000");

    // 4th row: reviewer (cost: 0, calls: 1)
    expect(rows[4]).toHaveTextContent("reviewer");
    expect(rows[4]).toHaveTextContent("1");
    expect(rows[4]).toHaveTextContent("$0.00000");
  });
});
