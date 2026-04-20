"use client";

import React from "react";

interface State {
  hasError: boolean;
  error?: Error;
}

interface Props {
  children: React.ReactNode;
  fallback?: (error: Error, reset: () => void) => React.ReactNode;
}

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    if (typeof window !== "undefined") {
      console.error("ErrorBoundary caught:", error, info);
    }
  }

  reset = () => {
    this.setState({ hasError: false, error: undefined });
  };

  render() {
    if (this.state.hasError && this.state.error) {
      if (this.props.fallback) {
        return this.props.fallback(this.state.error, this.reset);
      }
      return (
        <div className="p-6 bg-red-50 border border-red-200 rounded-xl max-w-2xl mx-auto my-8">
          <h2 className="text-lg font-bold text-red-700 mb-2">
            Ein Fehler ist aufgetreten
          </h2>
          <p className="text-sm text-red-600 mb-4">
            {this.state.error.message || "Unbekannter Fehler"}
          </p>
          <button
            onClick={this.reset}
            className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
          >
            Neu versuchen
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
