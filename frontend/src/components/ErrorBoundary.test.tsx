import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ErrorBoundary } from "./ErrorBoundary";

const ThrowError = ({ shouldThrow = true, message = "Test error" }: { shouldThrow?: boolean, message?: string }) => {
  if (shouldThrow) {
    throw new Error(message);
  }
  return <div>Normal Content</div>;
};

describe("ErrorBoundary", () => {
  // Prevent console.error from cluttering the test output
  const originalConsoleError = console.error;
  beforeEach(() => {
    console.error = vi.fn();
  });

  afterEach(() => {
    console.error = originalConsoleError;
  });

  it("renders children when there is no error", () => {
    render(
      <ErrorBoundary>
        <ThrowError shouldThrow={false} />
      </ErrorBoundary>
    );
    expect(screen.getByText("Normal Content")).toBeInTheDocument();
  });

  it("renders default fallback UI when a child component throws an error", () => {
    render(
      <ErrorBoundary>
        <ThrowError message="This is a test error" />
      </ErrorBoundary>
    );

    expect(screen.getByText("Something went wrong")).toBeInTheDocument();
    expect(screen.getByText("This is a test error")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();

    // Verify console.error was called due to the error boundary catching it
    expect(console.error).toHaveBeenCalled();
  });

  it("renders a custom fallback component when provided and a child component throws an error", () => {
    render(
      <ErrorBoundary fallback={<div>Custom Error Fallback</div>}>
        <ThrowError />
      </ErrorBoundary>
    );

    expect(screen.getByText("Custom Error Fallback")).toBeInTheDocument();
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
  });

  it("recovers and attempts to render children again when the Retry button is clicked", () => {
    let shouldThrow = true;

    const FlakyComponent = () => {
      if (shouldThrow) {
        throw new Error("Temporary error");
      }
      return <div>Recovered Content</div>;
    };

    render(
      <ErrorBoundary>
        <FlakyComponent />
      </ErrorBoundary>
    );

    // Initial render throws an error
    expect(screen.getByText("Something went wrong")).toBeInTheDocument();

    // Fix the component so it stops throwing
    shouldThrow = false;

    // In React testing library, clicking retry won't auto-rerender the tree with the new shouldThrow closure unless we rerender or wait
    // However, clicking retry calls setState({ hasError: false }), causing ErrorBoundary to re-render its children.
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));

    // Now it should successfully render the child
    expect(screen.getByText("Recovered Content")).toBeInTheDocument();
    expect(screen.queryByText("Something went wrong")).not.toBeInTheDocument();
  });
});
