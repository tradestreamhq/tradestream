package com.verlumen.tradestream.discovery

import org.json.JSONException
import org.json.JSONObject
import java.util.Base64

object StrategyCsvUtil {
    fun convertToCsvRow(element: DiscoveredStrategy): String? {
        val parametersAny = element.strategy.parameters

        // Convert Protocol Buffer Any to base64 and wrap in a JSON object
        val base64Data = Base64.getEncoder().encodeToString(parametersAny.toByteArray())
        val wrappedJson = JSONObject().put("base64_data", base64Data).toString()

        val hash =
            java.security.MessageDigest
                .getInstance(
                    "SHA-256",
                ).digest(parametersAny.toByteArray())
                .joinToString("") { "%02x".format(it) }

        val strategyName = element.strategy.strategyName

        return listOf(
            element.symbol,
            strategyName,
            wrappedJson,
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
            val jsonObj = JSONObject(json)
            // Check if it has the expected base64_data field
            if (!jsonObj.has("base64_data")) return false

            // Validate that the base64_data can be decoded
            val base64Data = jsonObj.getString("base64_data")
            Base64.getDecoder().decode(base64Data)
            true
        } catch (e: JSONException) {
            false
        } catch (e: IllegalArgumentException) {
            // Invalid base64
            false
        }
    }
}
