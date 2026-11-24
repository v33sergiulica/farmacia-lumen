import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error("Dashboard ErrorBoundary caught:", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="rounded-lg border border-[#FECDCA] bg-[#FEF3F2] p-6 text-[#111A16]">
          <h2 className="text-sm font-semibold text-[#B42318]">
            Unable to render this view
          </h2>
          <p className="mt-1 text-xs text-[#46544D]">{this.state.error.message}</p>
          <button
            type="button"
            onClick={() => this.setState({ error: null })}
            className="mt-4 rounded border border-[#E2E7E4] bg-white px-3 py-1.5 text-xs font-medium text-[#111A16] hover:bg-[#F6F7F6]"
          >
            Try Again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
