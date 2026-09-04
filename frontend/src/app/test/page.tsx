"use client";

import { useState, useEffect } from "react";
import Link from "next/link";

export default function AgentFlowDashboard() {
  const [logs, setLogs] = useState<{agent: string, detail: string, time: string}[]>([]);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);

  useEffect(() => {
    // Mocking real-time activity for the visual flow
    const interval = setInterval(() => {
      const agents = ["Manager Agent", "Sales Agent", "Billing Agent", "Support Agent"];
      const randomAgent = agents[Math.floor(Math.random() * agents.length)];
      setActiveAgent(randomAgent);
      setTimeout(() => setActiveAgent(null), 1500);
    }, 4000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div style={styles.container}>
      <header style={styles.header}>
        <h1 style={{ margin: 0, fontSize: "1.5rem" }}>Antigravity Agent OS</h1>
        <Link href="/" style={{ color: "var(--teal)", textDecoration: "none", fontWeight: 600 }}>← Back to Store</Link>
      </header>
      
      <main style={styles.main}>
        <div style={styles.canvas}>
          <h2 style={{ position: "absolute", top: 20, left: 30, color: "#cbd5e1" }}>Live Flow Execution (n8n style)</h2>
          
          <div style={styles.flowWrapper}>
            {/* User Node */}
            <div style={styles.nodeWrapper}>
              <div style={{...styles.node, ...styles.userNode}}>
                <span style={styles.icon}>👤</span> User Request
              </div>
            </div>

            {/* Down Arrow */}
            <div style={styles.arrow}>↓</div>

            {/* Manager Node (Supervisor) */}
            <div style={styles.nodeWrapper}>
              <div style={{
                ...styles.node, 
                ...styles.managerNode,
                ...(activeAgent === "Manager Agent" ? styles.activeNode : {})
              }}>
                <span style={styles.icon}>🛡️</span> Manager Agent (Supervisor)
              </div>
              <div style={styles.subtext}>Validates policy & routes session</div>
            </div>

            {/* Branching Arrows */}
            <div style={styles.branchContainer}>
              <div style={{...styles.branchArrow, transform: "rotate(-45deg)", left: "20%"}}>↘</div>
              <div style={{...styles.branchArrow, transform: "rotate(0deg)", left: "50%"}}>↓</div>
              <div style={{...styles.branchArrow, transform: "rotate(45deg)", left: "80%"}}>↙</div>
            </div>

            {/* Specialist Agents */}
            <div style={styles.specialistsRow}>
              <div style={styles.nodeWrapper}>
                <div style={{
                  ...styles.node, 
                  ...styles.specialistNode,
                  ...(activeAgent === "Sales Agent" ? styles.activeNode : {})
                }}>
                  <span style={styles.icon}>🛍️</span> Sales Agent
                </div>
                <div style={styles.subtext}>RAG Search & Cart</div>
              </div>

              <div style={styles.nodeWrapper}>
                <div style={{
                  ...styles.node, 
                  ...styles.specialistNode,
                  ...(activeAgent === "Billing Agent" ? styles.activeNode : {})
                }}>
                  <span style={styles.icon}>💳</span> Billing Agent
                </div>
                <div style={styles.subtext}>Razorpay API & Checkout</div>
              </div>

              <div style={styles.nodeWrapper}>
                <div style={{
                  ...styles.node, 
                  ...styles.specialistNode,
                  ...(activeAgent === "Support Agent" ? styles.activeNode : {})
                }}>
                  <span style={styles.icon}>🎧</span> Support Agent
                </div>
                <div style={styles.subtext}>Returns & Queries</div>
              </div>
            </div>

            {/* Converge Arrow */}
            <div style={{marginTop: "2rem"}}>
              <div style={styles.arrow}>↓</div>
            </div>

            {/* Manager Audit Node */}
            <div style={styles.nodeWrapper}>
              <div style={{
                ...styles.node, 
                ...styles.managerNode,
                ...(activeAgent === "Manager Agent" ? styles.activeNode : {})
              }}>
                <span style={styles.icon}>⚖️</span> Manager Agent (Audit)
              </div>
              <div style={styles.subtext}>Final Guardrail Check</div>
            </div>

            {/* Down Arrow */}
            <div style={styles.arrow}>↓</div>

            {/* Frontend Node */}
            <div style={styles.nodeWrapper}>
              <div style={{...styles.node, ...styles.userNode}}>
                <span style={styles.icon}>💻</span> Frontend Streaming (SSE)
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

const styles = {
  container: {
    minHeight: "100vh",
    backgroundColor: "#0f172a",
    color: "#f8fafc",
    fontFamily: "var(--font-body), sans-serif",
    display: "flex",
    flexDirection: "column" as const,
  },
  header: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    padding: "1rem 2rem",
    borderBottom: "1px solid #1e293b",
    backgroundColor: "#1e293b",
  },
  main: {
    flex: 1,
    position: "relative" as const,
    overflow: "hidden",
    backgroundImage: "radial-gradient(#334155 1px, transparent 1px)",
    backgroundSize: "24px 24px",
    display: "flex",
    justifyContent: "center",
    alignItems: "center",
  },
  canvas: {
    width: "100%",
    maxWidth: "1000px",
    height: "800px",
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    position: "relative" as const,
  },
  flowWrapper: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
    marginTop: "5rem",
    width: "100%",
  },
  nodeWrapper: {
    display: "flex",
    flexDirection: "column" as const,
    alignItems: "center",
  },
  node: {
    padding: "0.8rem 1.5rem",
    borderRadius: "8px",
    border: "1px solid",
    fontSize: "0.95rem",
    fontWeight: 600,
    display: "flex",
    alignItems: "center",
    gap: "0.5rem",
    boxShadow: "0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)",
    transition: "all 0.3s ease",
  },
  userNode: {
    backgroundColor: "#334155",
    borderColor: "#475569",
    color: "#e2e8f0",
  },
  managerNode: {
    backgroundColor: "#1e1b4b",
    borderColor: "#4f46e5",
    color: "#c7d2fe",
  },
  specialistNode: {
    backgroundColor: "#064e3b",
    borderColor: "#10b981",
    color: "#d1fae5",
    width: "180px",
    justifyContent: "center",
  },
  activeNode: {
    boxShadow: "0 0 0 4px rgba(79, 70, 229, 0.4)",
    transform: "scale(1.05)",
  },
  icon: {
    fontSize: "1.2rem",
  },
  subtext: {
    fontSize: "0.75rem",
    color: "#94a3b8",
    marginTop: "0.4rem",
  },
  arrow: {
    color: "#475569",
    fontSize: "1.5rem",
    margin: "0.5rem 0",
  },
  branchContainer: {
    display: "flex",
    justifyContent: "center",
    width: "600px",
    position: "relative" as const,
    height: "40px",
    margin: "1rem 0",
  },
  branchArrow: {
    color: "#475569",
    fontSize: "1.5rem",
    position: "absolute" as const,
    top: 0,
  },
  specialistsRow: {
    display: "flex",
    justifyContent: "center",
    gap: "2rem",
    width: "100%",
  },
};
