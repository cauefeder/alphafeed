import { Component } from "react";
import { T } from "../tokens.js";

/**
 * Catches render errors in child tab/chart components so one broken
 * panel never takes down the whole page.
 */
export class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error("[ErrorBoundary]", error, info?.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{
          borderRadius: 14, padding: "32px 20px", textAlign: "center",
          background: "rgba(239,68,68,.04)", border: "1px solid rgba(239,68,68,.18)",
          marginBottom: 16,
        }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: "#ef4444", marginBottom: 8 }}>
            Something went wrong rendering this section
          </div>
          <div style={{ fontSize: 11, color: T.dim, fontFamily: T.mono, marginBottom: 16 }}>
            {this.state.error?.message ?? "Unknown error"}
          </div>
          <button
            onClick={() => this.setState({ error: null })}
            style={{
              fontSize: 11, padding: "6px 14px", borderRadius: 8, cursor: "pointer",
              background: "rgba(239,68,68,.1)", color: "#ef4444",
              border: "1px solid rgba(239,68,68,.3)",
            }}
          >
            Retry
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
