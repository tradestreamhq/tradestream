package com.verlumen.tradestream.discovery

import java.util.Base64
import org.json.JSONObject
import org.json.JSONException

object StrategyCsvUtil {
    fun convertToCsvRow(element: DiscoveredStrategy): String? {
        val parametersAny = element.strategy.parameters
        if (parametersAny.value.isEmpty()) {
            return ""
        }
        val base64 = Base64.getEncoder().encodeToString(parametersAny.toByteArray())
        val json = "{" + "\"base64_data\": \"$base64\"}"
        val hash = java.security.MessageDigest.getInstance("SHA-256").digest(parametersAny.toByteArray()).joinToString("") { "%02x".format(it) }
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

    fun validateJsonParameter(json: String): Boolean {
        return try {
            JSONObject(json)
            true
        } catch (e: JSONException) {
            false
        }
    }
} 