package com.verlumen.tradestream.strategies.configurable.llm;

import com.google.gson.Gson;
import com.google.gson.GsonBuilder;
import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Client for the OpenRouter API. Sends chat completion requests and returns the generated text.
 */
public final class OpenRouterClient {
  private static final Logger logger = Logger.getLogger(OpenRouterClient.class.getName());
  private static final String API_URL = "https://openrouter.ai/api/v1/chat/completions";
  private static final Gson GSON = new GsonBuilder().create();

  private final String apiKey;
  private final String model;
  private final HttpClient httpClient;

  public OpenRouterClient(String apiKey, String model) {
    this.apiKey = apiKey;
    this.model = model;
    this.httpClient =
        HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(30)).build();
  }

  public OpenRouterClient(String apiKey) {
    this(apiKey, "anthropic/claude-sonnet-4-6");
  }

  /**
   * Send a chat completion request and return the generated text.
   *
   * @param systemPrompt The system prompt
   * @param userPrompt The user prompt
   * @param temperature Temperature for generation (0.0-1.0)
   * @param maxTokens Maximum tokens to generate
   * @return The generated text
   */
  public String chatCompletion(
      String systemPrompt, String userPrompt, double temperature, int maxTokens)
      throws IOException, InterruptedException {

    JsonObject requestBody = new JsonObject();
    requestBody.addProperty("model", model);
    requestBody.addProperty("temperature", temperature);
    requestBody.addProperty("max_tokens", maxTokens);

    JsonArray messages = new JsonArray();

    JsonObject systemMsg = new JsonObject();
    systemMsg.addProperty("role", "system");
    systemMsg.addProperty("content", systemPrompt);
    messages.add(systemMsg);

    JsonObject userMsg = new JsonObject();
    userMsg.addProperty("role", "user");
    userMsg.addProperty("content", userPrompt);
    messages.add(userMsg);

    requestBody.add("messages", messages);

    HttpRequest request =
        HttpRequest.newBuilder()
            .uri(URI.create(API_URL))
            .header("Content-Type", "application/json")
            .header("Authorization", "Bearer " + apiKey)
            .POST(HttpRequest.BodyPublishers.ofString(GSON.toJson(requestBody)))
            .timeout(Duration.ofSeconds(60))
            .build();

    HttpResponse<String> response =
        httpClient.send(request, HttpResponse.BodyHandlers.ofString());

    if (response.statusCode() != 200) {
      throw new IOException(
          "OpenRouter API error (HTTP " + response.statusCode() + "): " + response.body());
    }

    JsonObject responseJson = GSON.fromJson(response.body(), JsonObject.class);
    JsonArray choices = responseJson.getAsJsonArray("choices");
    if (choices == null || choices.isEmpty()) {
      throw new IOException("No choices in OpenRouter response");
    }

    return choices
        .get(0)
        .getAsJsonObject()
        .getAsJsonObject("message")
        .get("content")
        .getAsString()
        .trim();
  }
}
