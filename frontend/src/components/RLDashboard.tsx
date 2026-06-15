import { useState, useEffect } from "react";
import { api } from "../api/client";
import { Icon } from "./Icons";

interface ArmInfo {
  arm: string;
  reward: number;
  pulls: number;
  theta: number[];
}

interface FeedbackStat {
  arm: string;
  total_reward: number;
  count: number;
  avg_reward: number;
  source: string;
}

/** RL (reinforcement learning) dashboard showing LinUCB bandit state and feedback stats.
 *
 * Fetches data from api.rl.state() and api.feedback.stats().
 * Displays per-arm metrics, cumulative rewards, and pending buffer size.
 *
 * @example
 * <RLDashboard />
 */
export function RLDashboard() {
  const [arms, setArms] = useState<ArmInfo[]>([]);
  const [fbStats, setFbStats] = useState<FeedbackStat[]>([]);
  const [totalFeedbacks, setTotalFeedbacks] = useState(0);
  const [bufferSize, setBufferSize] = useState(0);
  const [batchSize, setBatchSize] = useState(10);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState("");

  useEffect(() => {
    Promise.all([
      api.rl.state(),
      api.feedback.stats(),
    ]).then(([rlRes, fbRes]) => {
      const raw = rlRes.data;
      const parsed: ArmInfo[] = [];
      if (raw.arms) {
        for (const [arm, info] of Object.entries(raw.arms)) {
          const i = info as Record<string, unknown>;
          parsed.push({
            arm,
            reward: (i.reward as number) || 0,
            pulls: (i.pulls as number) || 0,
            theta: (i.theta as number[]) || [],
          });
        }
      }
      setArms(parsed);
      setBatchSize(raw.config?.batch_size || 10);

      if (fbRes.data) {
        setFbStats(fbRes.data.per_arm || []);
        setTotalFeedbacks(fbRes.data.total_feedbacks || 0);
        setBufferSize(fbRes.data.buffer_size || 0);
      }
    }).catch((e) => {
      console.warn("RLDashboard: failed to fetch data", e);
      setFetchError("Could not load RL data. Backend may be unavailable.");
    }).finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="card">
        <div className="card-body" style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div className="spinner" />
          <span style={{ color: "var(--color-text-secondary)", fontSize: 13 }}>Loading RL state...</span>
        </div>
      </div>
    );
  }

  if (fetchError) {
    return (
      <div className="card" style={{ borderLeft: "4px solid var(--color-error)" }}>
        <div className="card-body" style={{ padding: "12px 16px", display: "flex", alignItems: "flex-start", gap: 12 }}>
          <Icon name="warning" size={16} />
          <div style={{ flex: 1, fontSize: 13, lineHeight: 1.5 }}>{fetchError}</div>
        </div>
      </div>
    );
  }

  const totalPulls = arms.reduce((s, a) => s + a.pulls, 0);
  const totalReward = arms.reduce((s, a) => s + a.reward, 0);

  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Reinforcement Learning Dashboard</h1>
        <p className="page-desc">LinUCB bandit state — agent selection, reward tracking, and human feedback</p>
      </div>

      <div className="stats-grid" style={{ marginBottom: 20 }}>
        <div className="stat-card">
          <div className="stat-label">Total Pulls</div>
          <div className="stat-value">{totalPulls}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Total Reward</div>
          <div className="stat-value">{totalReward.toFixed(4)}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Feedback Count</div>
          <div className="stat-value">{totalFeedbacks}</div>
        </div>
        <div className="stat-card">
          <div className="stat-label">Pending Buffer</div>
          <div className="stat-value" style={{ color: bufferSize > 0 ? "var(--color-warning)" : "var(--color-success)" }}>
            {bufferSize}/{batchSize}
          </div>
          <div className="stat-desc">Auto-flush at {batchSize}</div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 20 }}>
        <div className="card-header">
          <span className="card-title">Action Distribution (Bandit Arms)</span>
        </div>
        <div className="card-body" style={{ padding: 12 }}>
          {arms.length === 0 ? (
            <div className="empty-state">
              <div className="empty-state-text">No RL data available.</div>
            </div>
          ) : (
            <div className="trace-list">
              {arms.map((arm) => {
                const pct = totalPulls > 0 ? ((arm.pulls / totalPulls) * 100).toFixed(1) : "0.0";
                const avgReward = arm.pulls > 0 ? (arm.reward / arm.pulls).toFixed(4) : "0.0000";
                return (
                  <div key={arm.arm} className="trace-item">
                    <div className="trace-item-header">
                      <div className="trace-node-name" style={{ flex: 1 }}>
                        {arm.arm}
                      </div>
                      <span className="badge badge-info">{pct}%</span>
                    </div>
                    <div style={{ padding: "8px 12px", fontSize: 12, color: "var(--color-text-secondary)" }}>
                      <div>
                        Rewards: <strong>{arm.reward.toFixed(4)}</strong> &middot; Avg: <strong>{avgReward}</strong>
                      </div>
                      <div>
                        Pulls: <strong>{arm.pulls}</strong>
                      </div>
                      {arm.theta.length > 0 && (
                        <div style={{ marginTop: 2 }}>
                          Theta: [{arm.theta.slice(0, 4).map((v) => v.toFixed(2)).join(", ")}...]
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {fbStats.length > 0 && (
        <div className="card">
          <div className="card-header">
            <span className="card-title">Human Feedback Stats</span>
            <span className="badge badge-info">{totalFeedbacks} feedbacks</span>
          </div>
          <div className="card-body" style={{ padding: 0 }}>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Arm</th>
                  <th>Feedbacks</th>
                  <th>Total Reward</th>
                  <th>Avg Reward</th>
                  <th>Source</th>
                </tr>
              </thead>
              <tbody>
                {fbStats.map((s) => (
                  <tr key={s.arm}>
                    <td><span className="badge badge-info">{s.arm}</span></td>
                    <td>{s.count}</td>
                    <td>{s.total_reward.toFixed(4)}</td>
                    <td>{s.avg_reward.toFixed(4)}</td>
                    <td style={{ fontSize: 11 }}>{s.source}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
