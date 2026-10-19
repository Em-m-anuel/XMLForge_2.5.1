import React from "react";

type Props = {
  children: React.ReactNode;
  name?: string;
  onReset?: () => void;
};

type State = {
  hasError: boolean;
  error: Error | null;
};

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false, error: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error(`[ErrorBoundary:${this.props.name || "unknown"}]`, error, info);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
    this.props.onReset?.();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="rounded-lg border border-danger/30 bg-danger-soft p-6 text-center">
          <p className="text-[14px] font-medium text-danger">Cette section n'a pas pu être affichée.</p>
          <p className="mt-1 font-mono text-[11px] text-dim">
            {this.props.name ? `Zone: ${this.props.name}` : ""} {this.state.error?.message || ""}
          </p>
          <div className="mt-4 flex justify-center gap-2">
            <button
              onClick={this.handleRetry}
              className="rounded-md bg-surface px-3 py-1.5 text-[12px] font-medium text-fg border border-line hover:bg-raised"
            >
              Réessayer
            </button>
            <button
              onClick={() => window.history.back()}
              className="rounded-md bg-raised px-3 py-1.5 text-[12px] text-muted border border-line hover:bg-panel"
            >
              Retour
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}

export function withErrorBoundary<P extends object>(Component: React.ComponentType<P>, name: string) {
  return (props: P) => (
    <ErrorBoundary name={name}>
      <Component {...props} />
    </ErrorBoundary>
  );
}
