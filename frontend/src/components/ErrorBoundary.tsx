import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: { componentStack?: string }) {
    console.error("ErrorBoundary caught:", error, info?.componentStack);
  }

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <div className="card" style={{ borderLeft: "4px solid var(--color-error)" }}>
          <div className="card-body" style={{ padding: "12px 16px" }}>
            <div style={{ fontWeight: 600, marginBottom: 4, color: "var(--color-error)" }}>
              Something went wrong
            </div>
            <div style={{ fontSize: 12, color: "var(--color-text-secondary)", marginBottom: 8 }}>
              {this.state.error?.message || "Unknown error"}
            </div>
            <button
              className="btn btn-sm btn-secondary"
              onClick={() => this.setState({ hasError: false, error: null })}
            >
              Retry
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
