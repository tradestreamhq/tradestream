"""
Covariance matrix computation for strategy returns.
"""

import numpy as np


def compute_covariance_matrix(returns_matrix: np.ndarray) -> np.ndarray:
    """Compute the sample covariance matrix from a returns matrix.

    Args:
        returns_matrix: (T x N) array where T is periods and N is strategies.

    Returns:
        (N x N) covariance matrix.
    """
    return np.cov(returns_matrix, rowvar=False, ddof=1)


def compute_mean_returns(returns_matrix: np.ndarray) -> np.ndarray:
    """Compute mean returns per strategy.

    Args:
        returns_matrix: (T x N) array.

    Returns:
        (N,) array of mean returns.
    """
    return np.mean(returns_matrix, axis=0)


def shrink_covariance(cov: np.ndarray, shrinkage: float = 0.1) -> np.ndarray:
    """Apply Ledoit-Wolf-style constant-correlation shrinkage.

    Shrinks toward the diagonal (identity scaled by avg variance) to improve
    numerical stability with limited samples.

    Args:
        cov: (N x N) sample covariance matrix.
        shrinkage: shrinkage intensity in [0, 1].

    Returns:
        (N x N) shrunk covariance matrix.
    """
    n = cov.shape[0]
    avg_var = np.trace(cov) / n
    target = avg_var * np.eye(n)
    return (1 - shrinkage) * cov + shrinkage * target
