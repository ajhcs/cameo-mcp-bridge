package com.claude.cameo.bridge.util;

import com.sun.net.httpserver.HttpExchange;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.Reader;
import java.util.ArrayList;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Utility methods for parsing HTTP request data from {@link HttpExchange} objects.
 * <p>
 * Handles JSON body parsing, query-string parameter extraction, and path-segment
 * extraction for the bridge REST API.
 */
public class JsonHelper {

    /**
     * Parse the request body as a JSON object.
     *
     * @param exchange the HTTP exchange
     * @return parsed JsonObject
     * @throws IOException if reading fails or the body is not valid JSON
     */
    public static JsonObject parseBody(HttpExchange exchange) throws IOException {
        try (Reader reader = new InputStreamReader(exchange.getRequestBody(), StandardCharsets.UTF_8)) {
            return JsonParser.parseReader(reader).getAsJsonObject();
        }
    }

    /**
     * Parse the query string into a key-value map.
     * Duplicate keys are overwritten (last wins). Keys/values are URL-decoded.
     *
     * @param exchange the HTTP exchange
     * @return map of query parameters (empty if none)
     */
    public static Map<String, String> parseQuery(HttpExchange exchange) {
        Map<String, String> params = new HashMap<>();
        String query = exchange.getRequestURI().getRawQuery();
        if (query == null || query.isEmpty()) {
            return params;
        }
        for (String pair : query.split("&")) {
            int eq = pair.indexOf('=');
            if (eq > 0) {
                String key = java.net.URLDecoder.decode(pair.substring(0, eq), StandardCharsets.UTF_8);
                String val = java.net.URLDecoder.decode(pair.substring(eq + 1), StandardCharsets.UTF_8);
                params.put(key, val);
            }
        }
        return params;
    }

    /**
     * Extract a single path parameter that immediately follows a known prefix.
     * <p>
     * For example, given prefix {@code "/api/v1/elements/"} and path
     * {@code "/api/v1/elements/abc123/children"}, this returns {@code "abc123"}.
     *
     * @param exchange the HTTP exchange
     * @param prefix   the path prefix (must end with '/')
     * @return the extracted path segment, or null if not found
     */
    public static String extractPathParam(HttpExchange exchange, String prefix) {
        String path = exchange.getRequestURI().getPath();
        if (path.startsWith(prefix) && path.length() > prefix.length()) {
            String remainder = path.substring(prefix.length());
            int slash = remainder.indexOf('/');
            return slash > 0 ? remainder.substring(0, slash) : remainder;
        }
        return null;
    }

    /**
     * Extract the sub-path after the first path parameter segment.
     * <p>
     * For example, given prefix {@code "/api/v1/elements/"} and path
     * {@code "/api/v1/elements/abc123/stereotypes"}, this returns {@code "stereotypes"}.
     *
     * @param exchange the HTTP exchange
     * @param prefix   the path prefix (must end with '/')
     * @return the sub-path after the first segment, or null if not found
     */
    public static String extractSubPath(HttpExchange exchange, String prefix) {
        String path = exchange.getRequestURI().getPath();
        if (path.startsWith(prefix)) {
            String remainder = path.substring(prefix.length());
            int slash = remainder.indexOf('/');
            if (slash > 0 && slash < remainder.length() - 1) {
                return remainder.substring(slash + 1);
            }
        }
        return null;
    }

    /**
     * Extract a required non-empty string field from a JSON body.
     *
     * @param body the JSON object
     * @param key  the field name
     * @return the string value
     * @throws IllegalArgumentException if the field is missing or empty
     */
    public static String requireString(JsonObject body, String key) {
        if (!body.has(key) || body.get(key).isJsonNull()) {
            throw new IllegalArgumentException("Required field missing: " + key);
        }
        String value = body.get(key).getAsString();
        if (value.isEmpty()) {
            throw new IllegalArgumentException("Required field is empty: " + key);
        }
        return value;
    }

    /**
     * Extract an optional string field from a JSON body.
     *
     * @param body the JSON object
     * @param key  the field name
     * @return the string value, or null if missing, null, or empty
     */
    public static String optionalString(JsonObject body, String key) {
        if (!body.has(key) || body.get(key).isJsonNull()) {
            return null;
        }
        String value = body.get(key).getAsString();
        return value.isEmpty() ? null : value;
    }

    /**
     * Extract an optional array of strings from a JSON body.
     *
     * @param body the JSON object
     * @param key  the field name
     * @return the list value, or null if missing or null
     * @throws IllegalArgumentException if the field is not an array of strings
     */
    public static List<String> optionalStringList(JsonObject body, String key) {
        if (!body.has(key) || body.get(key).isJsonNull()) {
            return null;
        }
        if (!body.get(key).isJsonArray()) {
            throw new IllegalArgumentException(key + " must be an array of strings");
        }
        JsonArray array = body.getAsJsonArray(key);
        List<String> values = new ArrayList<>(array.size());
        for (JsonElement item : array) {
            if (!item.isJsonPrimitive() || !item.getAsJsonPrimitive().isString()) {
                throw new IllegalArgumentException(key + " must contain only strings");
            }
            String value = item.getAsString();
            if (value == null || value.isEmpty()) {
                throw new IllegalArgumentException(key + " must not contain empty strings");
            }
            values.add(value);
        }
        return values;
    }
}
