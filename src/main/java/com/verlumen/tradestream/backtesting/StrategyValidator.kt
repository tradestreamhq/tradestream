package com.verlumen.tradestream.backtesting

import com.google.common.flogger.FluentLogger

/**
 * Configuration for strategy validation thresholds.
 *
 * @param minOosSharpe Minimum out-of-sample Sharpe ratio required
 * @param maxSharpeDegradation Maximum allowed Sharpe degradation (OOS vs IS)
 * @param maxOosSharpeStdDev Maximum OOS Sharpe standard deviation (consistency)
 * @param minWindows Minimum number of walk-forward windows
 */
data class ValidationConfig(
    val minOosSharpe: Double = DEFAULT_MIN_OOS_SHARPE,
    val maxSharpeDegradation: Double = DEFAULT_MAX_SHARPE_DEGRADATION,
    val maxOosSharpeStdDev: Double = DEFAULT_MAX_OOS_SHARPE_STD_DEV,
    val minWindows: Int = DEFAULT_MIN_WINDOWS,
) {
    companion object {
        // Default thresholds based on industry best practices
        const val DEFAULT_MIN_OOS_SHARPE = 0.5
        const val DEFAULT_MAX_SHARPE_DEGRADATION = 0.5 // OOS must be >= 50% of IS
        const val DEFAULT_MAX_OOS_SHARPE_STD_DEV = 0.5 // Consistency requirement
        const val DEFAULT_MIN_WINDOWS = 3
    }
}

/**
 * Validation result with detailed reasoning.
 *
 * @param status Validation status (APPROVED or REJECTED)
 * @param reasons List of reasons for rejection (empty if approved)
 */
data class ValidationDecision(
    val status: ValidationStatus,
    val reasons: List<String>,
)

/**
 * Validates trading strategies based on walk-forward results.
 *
 * The validator acts as a gate to prevent overfit strategies from being deployed.
 * It applies configurable thresholds to determine if a strategy has demonstrated
 * genuine predictive ability on out-of-sample data.
 *
 * Key validation criteria:
 * 1. Minimum OOS Sharpe ratio - strategy must be profitable OOS
 * 2. Maximum Sharpe degradation - OOS performance must be close to IS
 * 3. OOS consistency - performance must be stable across windows
 * 4. Minimum windows - sufficient data for statistical confidence
 */
class StrategyValidator(
    private val config: ValidationConfig = ValidationConfig(),
) {
    companion object {
        private val logger = FluentLogger.forEnclosingClass()
    }

    /**
     * Validates a strategy based on its walk-forward results.
     *
     * @param result Walk-forward validation result
     * @return Validation decision with status and reasons
     */
    fun validate(result: WalkForwardResult): ValidationDecision {
        val rejectionReasons = mutableListOf<String>()

        // Check if we have enough windows
        if (result.windowsCount < config.minWindows) {
            rejectionReasons.add(
                "Insufficient windows: ${result.windowsCount} < ${config.minWindows}",
            )
        }

        // Check OOS Sharpe ratio
        if (result.outOfSampleSharpe < config.minOosSharpe) {
            rejectionReasons.add(
                String.format(
                    "OOS Sharpe too low: %.4f < %.4f",
                    result.outOfSampleSharpe,
                    config.minOosSharpe,
                ),
            )
        }

        // Check Sharpe degradation
        if (result.sharpeDegradation > config.maxSharpeDegradation) {
            rejectionReasons.add(
                String.format(
                    "Sharpe degradation too high: %.1f%% > %.1f%%",
                    result.sharpeDegradation * 100,
                    config.maxSharpeDegradation * 100,
                ),
            )
        }

        // Check OOS consistency
        if (result.oosSharpeStdDev > config.maxOosSharpeStdDev) {
            rejectionReasons.add(
                String.format(
                    "OOS Sharpe inconsistent: std_dev=%.4f > %.4f",
                    result.oosSharpeStdDev,
                    config.maxOosSharpeStdDev,
                ),
            )
        }

        val status =
            if (rejectionReasons.isEmpty()) {
                ValidationStatus.APPROVED
            } else {
                ValidationStatus.REJECTED
            }

        if (status == ValidationStatus.APPROVED) {
            logger.atInfo().log(
                "Strategy APPROVED: OOS Sharpe=%.4f, Degradation=%.1f%%, Consistency=%.4f",
                result.outOfSampleSharpe,
                result.sharpeDegradation * 100,
                result.oosSharpeStdDev,
            )
        } else {
            logger.atInfo().log(
                "Strategy REJECTED: %s",
                rejectionReasons.joinToString("; "),
            )
        }

        return ValidationDecision(status, rejectionReasons)
    }

    /**
     * Applies validation decision to a walk-forward result.
     *
     * @param result Original walk-forward result
     * @return Updated result with validation status and reasons
     */
    fun applyValidation(result: WalkForwardResult): WalkForwardResult {
        val decision = validate(result)

        return result
            .toBuilder()
            .setStatus(decision.status)
            .setRejectionReason(decision.reasons.joinToString("; "))
            .build()
    }

    /**
     * Creates a summary report of the validation.
     *
     * @param result Walk-forward result to summarize
     * @return Human-readable summary string
     */
    fun summarize(result: WalkForwardResult): String {
        val sb = StringBuilder()
        sb.appendLine("=== Walk-Forward Validation Summary ===")
        sb.appendLine()
        sb.appendLine("Windows: ${result.windowsCount}")
        sb.appendLine()
        sb.appendLine("In-Sample Metrics:")
        sb.appendLine("  Sharpe Ratio: ${String.format("%.4f", result.inSampleSharpe)}")
        sb.appendLine("  Return: ${String.format("%.2f%%", result.inSampleReturn * 100)}")
        sb.appendLine()
        sb.appendLine("Out-of-Sample Metrics:")
        sb.appendLine("  Sharpe Ratio: ${String.format("%.4f", result.outOfSampleSharpe)}")
        sb.appendLine("  Return: ${String.format("%.2f%%", result.outOfSampleReturn * 100)}")
        sb.appendLine("  Sharpe Std Dev: ${String.format("%.4f", result.oosSharpeStdDev)}")
        sb.appendLine()
        sb.appendLine("Degradation:")
        sb.appendLine("  Sharpe: ${String.format("%.1f%%", result.sharpeDegradation * 100)}")
        sb.appendLine("  Return: ${String.format("%.1f%%", result.returnDegradation * 100)}")
        sb.appendLine()
        sb.appendLine("Status: ${result.status}")
        if (result.rejectionReason.isNotEmpty()) {
            sb.appendLine("Reason: ${result.rejectionReason}")
        }
        sb.appendLine()

        // Validation thresholds
        sb.appendLine("Thresholds (current config):")
        sb.appendLine("  Min OOS Sharpe: ${config.minOosSharpe}")
        sb.appendLine("  Max Sharpe Degradation: ${String.format("%.0f%%", config.maxSharpeDegradation * 100)}")
        sb.appendLine("  Max OOS Sharpe StdDev: ${config.maxOosSharpeStdDev}")
        sb.appendLine("  Min Windows: ${config.minWindows}")

        return sb.toString()
    }
}
