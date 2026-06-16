"""LinUCB contextual bandit for reinforcement-learning-guided agent routing.

The LinUCB algorithm treats each agent (policy, action, anomaly, compliance) as an arm.
It builds a feature vector from the query context and selects the arm with the highest
upper-confidence-bound score, balancing exploration vs. exploitation.
"""

from __future__ import annotations

import logging
import math
import pickle
from pathlib import Path

import numpy as np

from backend.src.core.settings import settings

logger = logging.getLogger("hr_ops.rl")

_ACTION_DIM = 4
_FEATURE_DIM = 8
_PERSIST_PATH = Path("backend/data/rl_bandit.pkl")


class LinUCBAgent:
    """Contextual bandit using LinUCB for selecting the optimal agent arm."""

    def __init__(self, alpha: float | None = None, gamma: float | None = None):
        """Initialize the LinUCB bandit with feature dimension, action count, and configurable exploration/decay."""
        self.alpha = alpha or settings.rl_alpha
        self.gamma = gamma or settings.rl_gamma
        self.d = _FEATURE_DIM
        self.n_actions = _ACTION_DIM
        self.A = [np.identity(self.d) for _ in range(self.n_actions)]
        self.b = [np.zeros(self.d) for _ in range(self.n_actions)]

    def _arm_index(self, action: str) -> int:
        mapping = {"policy": 0, "action": 1, "anomaly": 2, "compliance": 3}
        return mapping.get(action, 0)

    def select_action(self, context: dict) -> str:
        """Choose the best arm (agent) given a context vector using the LinUCB policy."""
        x = self._build_context_vector(context)
        p_values = []
        for a in range(self.n_actions):
            A_inv = np.linalg.inv(self.A[a])
            theta = A_inv @ self.b[a]
            p = (theta @ x) + self.alpha * math.sqrt(x @ A_inv @ x)
            p_values.append(p)
        arm = int(np.argmax(p_values))
        mapping = ["policy", "action", "anomaly", "compliance"]
        selected = mapping[arm]
        logger.debug(
            "RL selected action=%s p_values=%s",
            selected,
            [round(p, 4) for p in p_values],
        )
        return selected

    def update(self, context: dict, action: str, reward: float):
        """Update the chosen arm's covariance matrix and reward vector with observed reward."""
        a = self._arm_index(action)
        x = self._build_context_vector(context)
        self.A[a] += np.outer(x, x)
        self.b[a] += reward * x
        logger.debug("RL update action=%s reward=%.4f", action, reward)

    def _build_context_vector(self, context: dict) -> np.ndarray:
        vec = np.zeros(self.d)
        classification_map = {
            "policy": 0,
            "action": 1,
            "anomaly": 2,
            "compliance": 3,
        }
        cls = context.get("classification", "policy")
        idx = classification_map.get(cls, 0)
        vec[idx] = 1.0
        vec[4] = len(context.get("query", "")) / 500
        vec[5] = float(context.get("query_complexity", 0))
        vec[6] = float(context.get("urgent", 0))
        vec[7] = 1.0
        return vec

    def save(self, path: Path | None = None):
        """Persist bandit parameters (A, b, alpha, gamma) to a pickle file."""
        p = path or _PERSIST_PATH
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "wb") as f:
            pickle.dump(
                {
                    "A": self.A,
                    "b": self.b,
                    "alpha": self.alpha,
                    "gamma": self.gamma,
                },
                f,
            )
        logger.info("RL bandit saved to %s", p)

    def load(self, path: Path | None = None):
        """Load bandit parameters from a pickle file if it exists."""
        p = path or _PERSIST_PATH
        if p.exists():
            with open(p, "rb") as f:
                data = pickle.load(f)
            self.A = data["A"]
            self.b = data["b"]
            self.alpha = data.get("alpha", self.alpha)
            self.gamma = data.get("gamma", self.gamma)
            logger.info("RL bandit loaded from %s", p)


    def get_state(self) -> dict:
        """Return a snapshot of all arms' theta, pull count, and cumulative reward."""
        mapping = ["policy", "action", "anomaly", "compliance"]
        arms = {}
        for i, name in enumerate(mapping):
            theta = (np.linalg.inv(self.A[i]) @ self.b[i]).tolist()
            arms[name] = {"theta": theta, "pulls": int(np.trace(self.A[i]) - self.d), "reward": float(self.b[i].sum())}
        return {"arms": arms, "config": {"batch_size": settings.rl_batch_size, "alpha": self.alpha, "gamma": self.gamma}}


rl_agent = LinUCBAgent()
try:
    rl_agent.load()
except Exception as e:
    logger.warning("Failed to load RL bandit from disk, starting fresh: %s", e)


# ─── Anomaly Action Bandit ────────────────────────────────────────────────────

_ANOMALY_ACTIONS = ["escalate_hr_review", "flag_for_review", "request_manager_review",
                    "send_notification", "initiate_pip", "ignore"]
_ANOMALY_FEATURE_DIM = 10
_ANOMALY_PERSIST_PATH = Path("backend/data/anomaly_bandit.pkl")


class AnomalyActionBandit:
    """LinUCB bandit that selects the best remediation action for a detected anomaly.

    Arms (6): escalate_hr_review | flag_for_review | request_manager_review |
              send_notification | initiate_pip | ignore

    Feature vector (10-d):
      [0-5] one-hot action hint from rule engine
      [6]   anomaly confidence score (0–1)
      [7]   anomaly severity (0–1)
      [8]   is_payroll (1/0)
      [9]   is_leave (1/0)
    """

    def __init__(self, alpha: float = 0.8):
        self.alpha = alpha
        self.d = _ANOMALY_FEATURE_DIM
        self.n_actions = len(_ANOMALY_ACTIONS)
        self.A = [np.identity(self.d) for _ in range(self.n_actions)]
        self.b = [np.zeros(self.d) for _ in range(self.n_actions)]
        self._action_idx = {a: i for i, a in enumerate(_ANOMALY_ACTIONS)}

    def _build_feature(self, anomaly_context: dict) -> np.ndarray:
        vec = np.zeros(self.d)
        # One-hot hint from rule's recommended_action
        hint = anomaly_context.get("recommended_action", "flag_for_review")
        hint_idx = self._action_idx.get(hint, 1)
        vec[hint_idx] = 1.0
        vec[6] = float(anomaly_context.get("confidence_score", 0.7))
        vec[7] = float(anomaly_context.get("severity", 0.5))
        atype = anomaly_context.get("anomaly_type", "")
        vec[8] = 1.0 if "payroll" in atype.lower() else 0.0
        vec[9] = 1.0 if "leave" in atype.lower() else 0.0
        return vec

    def select_action(self, anomaly_context: dict) -> str:
        x = self._build_feature(anomaly_context)
        p_values = []
        for a in range(self.n_actions):
            A_inv = np.linalg.inv(self.A[a])
            theta = A_inv @ self.b[a]
            p = (theta @ x) + self.alpha * math.sqrt(max(float(x @ A_inv @ x), 0))
            p_values.append(p)
        arm = int(np.argmax(p_values))
        selected = _ANOMALY_ACTIONS[arm]
        logger.debug("AnomalyBandit selected=%s confidence=%.2f severity=%.2f",
                     selected, anomaly_context.get("confidence_score", 0),
                     anomaly_context.get("severity", 0))
        return selected

    def update(self, anomaly_context: dict, action: str, reward: float):
        a = self._action_idx.get(action, 1)
        x = self._build_feature(anomaly_context)
        self.A[a] += np.outer(x, x)
        self.b[a] += reward * x
        logger.debug("AnomalyBandit update action=%s reward=%.3f", action, reward)

    def save(self, path: Path | None = None):
        p = path or _ANOMALY_PERSIST_PATH
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "wb") as f:
            pickle.dump({"A": self.A, "b": self.b, "alpha": self.alpha}, f)
        logger.info("AnomalyBandit saved to %s", p)

    def load(self, path: Path | None = None):
        p = path or _ANOMALY_PERSIST_PATH
        if p.exists():
            with open(p, "rb") as f:
                data = pickle.load(f)
            self.A = data["A"]
            self.b = data["b"]
            self.alpha = data.get("alpha", self.alpha)
            logger.info("AnomalyBandit loaded from %s", p)

    def get_state(self) -> dict:
        arms = {}
        for i, name in enumerate(_ANOMALY_ACTIONS):
            theta = (np.linalg.inv(self.A[i]) @ self.b[i]).tolist()
            arms[name] = {
                "theta": theta,
                "pulls": int(np.trace(self.A[i]) - self.d),
                "reward": float(self.b[i].sum()),
            }
        return {"arms": arms, "config": {"alpha": self.alpha, "actions": _ANOMALY_ACTIONS}}


anomaly_bandit = AnomalyActionBandit()
try:
    anomaly_bandit.load()
except Exception as e:
    logger.warning("Failed to load AnomalyBandit from disk, starting fresh: %s", e)
