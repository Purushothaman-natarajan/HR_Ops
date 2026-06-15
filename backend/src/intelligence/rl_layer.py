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

from backend.config.settings import settings

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
