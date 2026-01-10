package com.verlumen.tradestream.backtesting

import com.google.common.truth.Truth.assertThat
import org.junit.Before
import org.junit.Test
import org.junit.runner.RunWith
import org.junit.runners.JUnit4

@RunWith(JUnit4::class)
class StrategyValidatorTest {
    private lateinit var validator: StrategyValidator
    private lateinit var strictValidator: StrategyValidator

    @Before
    fun setUp() {
        validator = StrategyValidator()
        strictValidator =
            StrategyValidator(
                ValidationConfig(
                    minOosSharpe = 1.0,
                    maxSharpeDegradation = 0.3,
                    maxOosSharpeStdDev = 0.3,
                    minWindows = 5,
                ),
            )
    }

    @Test
    fun validate_withGoodMetrics_returnsApproved() {
        // Arrange
        val result =
            WalkForwardResult
                .newBuilder()
                .setWindowsCount(5)
                .setInSampleSharpe(1.5)
                .setOutOfSampleSharpe(1.2)
                .setSharpeDegradation(0.2) // 20% degradation
                .setOosSharpeStdDev(0.3)
                .build()

        // Act
        val decision = validator.validate(result)

        // Assert
        assertThat(decision.status).isEqualTo(ValidationStatus.APPROVED)
        assertThat(decision.reasons).isEmpty()
    }

    @Test
    fun validate_withLowOosSharpe_returnsRejected() {
        // Arrange: OOS Sharpe below minimum threshold of 0.5
        val result =
            WalkForwardResult
                .newBuilder()
                .setWindowsCount(5)
                .setInSampleSharpe(1.5)
                .setOutOfSampleSharpe(0.3) // Below 0.5 threshold
                .setSharpeDegradation(0.8)
                .setOosSharpeStdDev(0.3)
                .build()

        // Act
        val decision = validator.validate(result)

        // Assert
        assertThat(decision.status).isEqualTo(ValidationStatus.REJECTED)
        assertThat(decision.reasons).hasSize(2) // Low Sharpe and high degradation
        assertThat(decision.reasons.first()).contains("OOS Sharpe too low")
    }

    @Test
    fun validate_withHighSharpeDegradation_returnsRejected() {
        // Arrange: Sharpe degradation above 50%
        val result =
            WalkForwardResult
                .newBuilder()
                .setWindowsCount(5)
                .setInSampleSharpe(2.0)
                .setOutOfSampleSharpe(0.8) // Good OOS, but...
                .setSharpeDegradation(0.6) // 60% degradation (above 50% threshold)
                .setOosSharpeStdDev(0.2)
                .build()

        // Act
        val decision = validator.validate(result)

        // Assert
        assertThat(decision.status).isEqualTo(ValidationStatus.REJECTED)
        assertThat(decision.reasons.any { it.contains("degradation too high") }).isTrue()
    }

    @Test
    fun validate_withInconsistentOosSharpe_returnsRejected() {
        // Arrange: High standard deviation in OOS Sharpe
        val result =
            WalkForwardResult
                .newBuilder()
                .setWindowsCount(5)
                .setInSampleSharpe(1.5)
                .setOutOfSampleSharpe(1.0)
                .setSharpeDegradation(0.33)
                .setOosSharpeStdDev(0.7) // Above 0.5 threshold
                .build()

        // Act
        val decision = validator.validate(result)

        // Assert
        assertThat(decision.status).isEqualTo(ValidationStatus.REJECTED)
        assertThat(decision.reasons.any { it.contains("inconsistent") }).isTrue()
    }

    @Test
    fun validate_withInsufficientWindows_returnsRejected() {
        // Arrange: Less than minimum required windows
        val result =
            WalkForwardResult
                .newBuilder()
                .setWindowsCount(2) // Below default minimum of 3
                .setInSampleSharpe(1.5)
                .setOutOfSampleSharpe(1.2)
                .setSharpeDegradation(0.2)
                .setOosSharpeStdDev(0.2)
                .build()

        // Act
        val decision = validator.validate(result)

        // Assert
        assertThat(decision.status).isEqualTo(ValidationStatus.REJECTED)
        assertThat(decision.reasons.any { it.contains("Insufficient windows") }).isTrue()
    }

    @Test
    fun validate_withMultipleFailures_reportsAllReasons() {
        // Arrange: Multiple validation failures
        val result =
            WalkForwardResult
                .newBuilder()
                .setWindowsCount(2) // Insufficient
                .setInSampleSharpe(2.0)
                .setOutOfSampleSharpe(0.3) // Too low
                .setSharpeDegradation(0.85) // Too high
                .setOosSharpeStdDev(0.8) // Too inconsistent
                .build()

        // Act
        val decision = validator.validate(result)

        // Assert
        assertThat(decision.status).isEqualTo(ValidationStatus.REJECTED)
        assertThat(decision.reasons).hasSize(4) // All four criteria failed
    }

    @Test
    fun validate_withStrictConfig_requiresHigherThresholds() {
        // Arrange: Good metrics for default, but not for strict
        val result =
            WalkForwardResult
                .newBuilder()
                .setWindowsCount(4) // Default passes (3), strict fails (5)
                .setInSampleSharpe(1.5)
                .setOutOfSampleSharpe(0.8) // Default passes (0.5), strict fails (1.0)
                .setSharpeDegradation(0.4) // Default passes (0.5), strict fails (0.3)
                .setOosSharpeStdDev(0.4) // Default passes (0.5), strict fails (0.3)
                .build()

        // Act
        val defaultDecision = validator.validate(result)
        val strictDecision = strictValidator.validate(result)

        // Assert
        assertThat(defaultDecision.status).isEqualTo(ValidationStatus.APPROVED)
        assertThat(strictDecision.status).isEqualTo(ValidationStatus.REJECTED)
    }

    @Test
    fun applyValidation_updatesResultStatus() {
        // Arrange
        val pendingResult =
            WalkForwardResult
                .newBuilder()
                .setStatus(ValidationStatus.PENDING)
                .setWindowsCount(5)
                .setInSampleSharpe(1.5)
                .setOutOfSampleSharpe(1.2)
                .setSharpeDegradation(0.2)
                .setOosSharpeStdDev(0.2)
                .build()

        // Act
        val validatedResult = validator.applyValidation(pendingResult)

        // Assert
        assertThat(validatedResult.status).isEqualTo(ValidationStatus.APPROVED)
        assertThat(validatedResult.rejectionReason).isEmpty()
    }

    @Test
    fun applyValidation_setsRejectionReason() {
        // Arrange
        val pendingResult =
            WalkForwardResult
                .newBuilder()
                .setStatus(ValidationStatus.PENDING)
                .setWindowsCount(5)
                .setInSampleSharpe(2.0)
                .setOutOfSampleSharpe(0.3) // Below threshold
                .setSharpeDegradation(0.2)
                .setOosSharpeStdDev(0.2)
                .build()

        // Act
        val validatedResult = validator.applyValidation(pendingResult)

        // Assert
        assertThat(validatedResult.status).isEqualTo(ValidationStatus.REJECTED)
        assertThat(validatedResult.rejectionReason).contains("OOS Sharpe too low")
    }

    @Test
    fun summarize_producesReadableOutput() {
        // Arrange
        val result =
            WalkForwardResult
                .newBuilder()
                .setStatus(ValidationStatus.APPROVED)
                .setWindowsCount(5)
                .setInSampleSharpe(1.5)
                .setOutOfSampleSharpe(1.2)
                .setSharpeDegradation(0.2)
                .setOosSharpeStdDev(0.25)
                .setInSampleReturn(0.15)
                .setOutOfSampleReturn(0.12)
                .setReturnDegradation(0.2)
                .build()

        // Act
        val summary = validator.summarize(result)

        // Assert
        assertThat(summary).contains("Walk-Forward Validation Summary")
        assertThat(summary).contains("Windows: 5")
        assertThat(summary).contains("In-Sample")
        assertThat(summary).contains("Out-of-Sample")
        assertThat(summary).contains("Status: APPROVED")
    }
}
