import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertCircle, RefreshCw } from "lucide-react";
import { Card } from "@/components/shared/Card";
import { reportError } from "@/lib/telemetry";

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
  label?: string;
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

  override componentDidCatch(error: Error, info: ErrorInfo): void {
    if (typeof console !== "undefined") {
      console.error("ErrorBoundary caught:", error, info.componentStack);
    }
    // Ship it. The console line only ever helped whoever had DevTools open —
    // which is never the user who actually hit the crash.
    reportError(error, { componentStack: info.componentStack ?? undefined });
  }

  override render() {
    if (this.state.hasError) {
      if (this.props.fallback) return this.props.fallback;
      return (
        <Card className="m-4 flex flex-col items-center gap-3 p-6 text-center">
          <AlertCircle className="h-6 w-6 text-bear" />
          <h3 className="text-sm font-semibold text-text-primary">
            {this.props.label ?? "Something went wrong"}
          </h3>
          <p className="max-w-md text-xs text-text-secondary">
            {this.state.error?.message ??
              "An unexpected error occurred while rendering this section."}
          </p>
          <button
            type="button"
            onClick={() => this.setState({ hasError: false, error: null })}
            className="flex items-center gap-1.5 rounded-[6px] border border-border bg-surface px-3 py-1.5 text-xs font-medium text-text-primary transition hover:bg-hover"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Try again
          </button>
        </Card>
      );
    }
    return this.props.children;
  }
}
