import { Component } from "react";

/** Isolates a failure (e.g. WebGL unavailable for the globe) to the panel
 * that broke, instead of letting one uncaught render error blank the
 * entire dashboard. */
export default class ErrorBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error) {
    console.error("Panel crashed:", error);
  }

  render() {
    if (this.state.failed) {
      return this.props.fallback ?? <div className="empty-hint">Komponente nicht verfügbar.</div>;
    }
    return this.props.children;
  }
}
