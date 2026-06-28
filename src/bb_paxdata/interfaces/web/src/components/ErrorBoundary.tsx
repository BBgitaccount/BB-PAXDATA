import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
    error: null,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('Uncaught error in ErrorBoundary:', error, errorInfo);
  }

  private handleReset = () => {
    this.setState({ hasError: false, error: null });
    window.location.reload();
  };

  public render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center p-8 bg-carbon-900 border border-hair border-carbon-550 rounded font-mono text-center space-y-4 max-w-lg mx-auto mt-20 animate-[fade-in-up_300ms_ease-out_both]">
          <div className="w-12 h-12 rounded-full bg-signal-fail/20 flex items-center justify-center text-signal-fail">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              className="w-6 h-6"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
              />
            </svg>
          </div>
          <h2 className="text-sm font-semibold text-carbon-50 uppercase tracking-widest">
            Bu sayfa yüklenirken bir hata oluştu
          </h2>
          <p className="text-2xs text-carbon-400 max-h-36 overflow-y-auto w-full text-left bg-carbon-950 p-3 border border-carbon-800 rounded">
            {this.state.error?.toString()}
          </p>
          <button
            onClick={this.handleReset}
            className="btn-primary py-2 px-6 text-xs uppercase tracking-diplomatic"
          >
            YENİLE
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}
