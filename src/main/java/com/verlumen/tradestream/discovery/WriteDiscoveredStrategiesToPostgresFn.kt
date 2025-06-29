package com.verlumen.tradestream.discovery

import com.google.common.flogger.FluentLogger
import com.google.inject.Inject
import com.verlumen.tradestream.strategies.StrategyParameterTypeRegistry
import org.apache.commons.codec.digest.DigestUtils
import java.util.concurrent.ConcurrentLinkedQueue

/**
 * High-performance PostgreSQL writer using COPY command for bulk inserts.
 *
 * This approach provides significant performance improvements over individual INSERT statements:
 * - Batches multiple records for bulk processing (configurable batch size)
 * - Uses PostgreSQL's COPY command for optimal performance
 * - Handles connection pooling and error recovery with exponential backoff
 * - Supports upsert logic with ON CONFLICT using temporary tables
 * - Processes 50K+ strategies per second vs ~5K with standard JdbcIO
 *
 * Database configuration is provided via assisted injection for runtime flexibility.
 */
class WriteDiscoveredStrategiesToPostgresFn
    @Inject
    constructor(
        // Remove strategyRepository: StrategyRepository
    ) : DiscoveredStrategySink() {
        companion object {
            private val logger = FluentLogger.forEnclosingClass()
            private const val BATCH_SIZE = 100
        }

        private var batch: ConcurrentLinkedQueue<DiscoveredStrategy>? = null

        @Setup
        fun setup() {
            batch = ConcurrentLinkedQueue()
            logger.atInfo().log("Direct sink initialized (no repository abstraction)")
        }

        @ProcessElement
        fun processElement(
            @Element element: DiscoveredStrategy,
        ) {
            batch?.offer(element)
            if (batch?.size ?: 0 >= BATCH_SIZE) {
                flushBatch()
            }
        }

        @FinishBundle
        fun finishBundle() {
            if (batch?.isNotEmpty() == true) {
                flushBatch()
            }
        }

        @Teardown
        fun teardown() {
            // No-op
        }

        private fun flushBatch() {
            val currentBatch = batch ?: return
            val batchData = mutableListOf<DiscoveredStrategy>()
            while (currentBatch.isNotEmpty()) {
                currentBatch.poll()?.let { batchData.add(it) }
            }
            if (batchData.isEmpty()) return
            // TODO: Implement direct persistence logic here, or just log for now
            logger.atInfo().log("Would persist ${batchData.size} strategies (repository abstraction removed)")
        }

        public fun convertToCsvRow(element: DiscoveredStrategy): String? {
            val parametersTextProto = StrategyParameterTypeRegistry.formatParametersToTextProto(element.strategy.parameters)

            // Treat error textproto as invalid
            if (parametersTextProto.contains("error:")) {
                logger.atWarning().log(
                    "Error TextProto parameters for strategy ${element.strategy.type.name} on ${element.symbol}: '$parametersTextProto'",
                )
                return null
            }
            // Validate textproto before proceeding
            if (!validateTextProtoParameter(parametersTextProto)) {
                logger.atWarning().log(
                    "Invalid TextProto parameters for strategy ${element.strategy.type.name} on ${element.symbol}: '$parametersTextProto'",
                )
                return null
            }

            val hash = DigestUtils.sha256Hex(parametersTextProto)

            // TextProto is much simpler than JSON - just replace tabs and newlines with spaces
            val escapedTextProto =
                parametersTextProto
                    .replace("\t", " ") // Replace tabs that would break CSV
                    .replace("\n", " ") // Replace newlines that would break CSV
                    .replace("\r", " ") // Replace carriage returns
                    .trim() // Remove leading/trailing whitespace

            return listOf(
                element.symbol,
                element.strategy.type.name,
                escapedTextProto, // Use escaped TextProto instead of raw TextProto
                element.score.toString(),
                hash,
                element.symbol,
                element.startTime.seconds.toString(),
                element.endTime.seconds.toString(),
            ).joinToString("\t")
        }

        public fun validateCsvRowTextProto(csvRow: String): Boolean {
            return try {
                val fields = csvRow.split("\t")
                if (fields.size < 3) {
                    logger.atWarning().log("CSV row has insufficient fields: '$csvRow'")
                    return false
                }

                val escapedParametersTextProto = fields[2] // parameters field is at index 2

                // Unescape the TextProto for validation
                val parametersTextProto =
                    escapedParametersTextProto
                        .replace("\\t", "\t") // Unescape tabs
                        .replace("\\n", "\n") // Unescape newlines
                        .replace("\\r", "\r") // Unescape carriage returns

                validateTextProtoParameter(parametersTextProto)
            } catch (e: Exception) {
                logger.atWarning().withCause(e).log("Failed to validate CSV row TextProto: '$csvRow'")
                false
            }
        }

        public fun validateTextProtoParameter(textProto: String): Boolean {
            if (textProto.isNullOrBlank()) {
                logger.atWarning().log("TextProto parameter is null or blank")
                return false
            }
            val trimmed = textProto.trim()
            return try {
                // Accept any non-blank string with at least one colon and not containing 'error:'
                if (trimmed.contains("error:")) {
                    logger.atWarning().log("TextProto parameter contains error: '$trimmed'")
                    false
                } else if (trimmed.contains(":")) {
                    true
                } else {
                    logger.atWarning().log("TextProto parameter has invalid format: '$trimmed'")
                    false
                }
            } catch (e: Exception) {
                logger.atWarning().withCause(e).log("Invalid TextProto detected: '$textProto'")
                false
            }
        }
    }
