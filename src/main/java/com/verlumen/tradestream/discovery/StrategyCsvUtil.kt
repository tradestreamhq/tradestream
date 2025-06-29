package com.verlumen.tradestream.discovery

import com.verlumen.tradestream.strategies.StrategyParameterTypeRegistry
import org.json.JSONException
import org.json.JSONObject
import java.util.Base64

object StrategyCsvUtil {
    fun convertToCsvRow(element: DiscoveredStrategy): String? {
        val parametersAny = element.strategy.parameters
        val json = StrategyParameterTypeRegistry.formatParametersToJson(parametersAny)
        val hash =
            java.security.MessageDigest
                .getInstance(
                    "SHA-256",
                ).digest(parametersAny.toByteArray())
                .joinToString("") { "%02x".format(it) }
        return listOf(
            element.symbol,
            element.strategy.type.name,
            json,
            element.score.toString(),
            hash,
            element.symbol,
            element.startTime.seconds.toString(),
            element.endTime.seconds.toString(),
        ).joinToString("\t")
    }

    fun validateCsvRowJson(csvRow: String): Boolean {
        val fields = csvRow.split("\t")
        if (fields.size < 3) return false
        val json = fields[2]
        return validateJsonParameter(json)
    }

    fun validateJsonParameter(json: String): Boolean =
        try {
            JSONObject(json)
            true
        } catch (e: JSONException) {
            false
        }
}
