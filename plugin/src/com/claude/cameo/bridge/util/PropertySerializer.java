package com.claude.cameo.bridge.util;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonNull;
import com.google.gson.JsonObject;
import com.google.gson.JsonPrimitive;
import com.nomagic.magicdraw.properties.Property;
import com.nomagic.magicdraw.properties.PropertyManager;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element;

import java.lang.reflect.Method;
import java.util.Collection;
import java.util.List;
import java.util.Map;

/**
 * Best-effort serializer for MagicDraw property managers.
 */
public final class PropertySerializer {

    private PropertySerializer() {
    }

    public static JsonObject serializeManager(PropertyManager manager, boolean includeRaw, boolean summaryOnly) {
        JsonObject json = new JsonObject();
        JsonArray properties = new JsonArray();
        JsonArray warnings = new JsonArray();

        if (manager == null) {
            json.addProperty("propertyCount", 0);
            json.add("properties", properties);
            warnings.add("PropertyManager was null");
            json.add("warnings", warnings);
            return json;
        }

        json.addProperty("className", manager.getClass().getName());
        try {
            @SuppressWarnings("unchecked")
            List<Property> managerProperties = manager.getProperties();
            if (managerProperties != null) {
                for (Property property : managerProperties) {
                    properties.add(serializeProperty(property, includeRaw, summaryOnly));
                }
            }
        } catch (Exception e) {
            warnings.add("Could not read properties: " + e.getClass().getSimpleName() + ": " + e.getMessage());
        }

        json.addProperty("propertyCount", properties.size());
        json.add("properties", properties);
        if (warnings.size() > 0) {
            json.add("warnings", warnings);
        }
        return json;
    }

    public static JsonObject serializeProperty(Property property, boolean includeRaw, boolean summaryOnly) {
        JsonObject json = new JsonObject();
        JsonArray warnings = new JsonArray();
        if (property == null) {
            json.add("value", JsonNull.INSTANCE);
            warnings.add("Property was null");
            json.add("warnings", warnings);
            return json;
        }

        safeAddString(json, "name", () -> property.getName(), warnings);
        safeAddString(json, "id", () -> property.getID(), warnings);
        safeAddString(json, "classType", () -> property.getClassType(), warnings);
        json.addProperty("propertyClassName", property.getClass().getName());

        Object value = null;
        try {
            value = property.getValue();
            json.add("value", serializeValue(value, includeRaw, summaryOnly));
            json.addProperty("valueType", value != null ? value.getClass().getName() : "null");
            json.addProperty("valueString", value != null ? String.valueOf(value) : null);
        } catch (Exception e) {
            warnings.add("Could not read value: " + e.getClass().getSimpleName() + ": " + e.getMessage());
            json.add("value", JsonNull.INSTANCE);
        }

        if (includeRaw && value != null) {
            JsonObject raw = new JsonObject();
            raw.addProperty("className", value.getClass().getName());
            raw.addProperty("string", String.valueOf(value));
            json.add("raw", raw);
        }
        if (warnings.size() > 0) {
            json.add("warnings", warnings);
        }
        return json;
    }

    public static JsonElement serializeValue(Object value, boolean includeRaw, boolean summaryOnly) {
        if (value == null) {
            return JsonNull.INSTANCE;
        }
        if (value instanceof String) {
            return new JsonPrimitive((String) value);
        }
        if (value instanceof Number) {
            return new JsonPrimitive((Number) value);
        }
        if (value instanceof Boolean) {
            return new JsonPrimitive((Boolean) value);
        }
        if (value instanceof Character) {
            return new JsonPrimitive((Character) value);
        }
        if (value instanceof Element) {
            return ElementSerializer.toJsonCompact((Element) value);
        }
        if (value instanceof Collection<?>) {
            JsonArray array = new JsonArray();
            if (!summaryOnly) {
                int count = 0;
                for (Object item : (Collection<?>) value) {
                    if (count++ >= 250) {
                        break;
                    }
                    array.add(serializeValue(item, includeRaw, true));
                }
            }
            JsonObject wrapper = new JsonObject();
            wrapper.addProperty("collectionType", value.getClass().getName());
            wrapper.addProperty("count", ((Collection<?>) value).size());
            wrapper.add("items", array);
            return wrapper;
        }
        if (value instanceof Map<?, ?>) {
            JsonObject wrapper = new JsonObject();
            wrapper.addProperty("mapType", value.getClass().getName());
            wrapper.addProperty("count", ((Map<?, ?>) value).size());
            if (!summaryOnly) {
                JsonObject entries = new JsonObject();
                int count = 0;
                for (Map.Entry<?, ?> entry : ((Map<?, ?>) value).entrySet()) {
                    if (count++ >= 250) {
                        break;
                    }
                    entries.add(String.valueOf(entry.getKey()), serializeValue(entry.getValue(), includeRaw, true));
                }
                wrapper.add("entries", entries);
            }
            return wrapper;
        }

        JsonObject fallback = new JsonObject();
        fallback.addProperty("className", value.getClass().getName());
        fallback.addProperty("string", String.valueOf(value));
        if (includeRaw) {
            appendNoArgGetterValues(fallback, value);
        }
        return fallback;
    }

    private static void appendNoArgGetterValues(JsonObject json, Object value) {
        JsonObject getters = new JsonObject();
        for (Method method : value.getClass().getMethods()) {
            if (method.getParameterCount() != 0 || method.getReturnType() == Void.TYPE) {
                continue;
            }
            String name = method.getName();
            if (!name.startsWith("get") && !name.startsWith("is")) {
                continue;
            }
            if ("getClass".equals(name)) {
                continue;
            }
            try {
                Object result = method.invoke(value);
                getters.add(name, serializeValue(result, false, true));
            } catch (Exception ignored) {
                // Reflection dumps are diagnostic; inaccessible getters are expected.
            }
        }
        if (getters.size() > 0) {
            json.add("getterValues", getters);
        }
    }

    private static void safeAddString(JsonObject json, String key, StringSupplier supplier, JsonArray warnings) {
        try {
            String value = supplier.get();
            if (value != null) {
                json.addProperty(key, value);
            }
        } catch (Exception e) {
            warnings.add("Could not read " + key + ": " + e.getClass().getSimpleName() + ": " + e.getMessage());
        }
    }

    @FunctionalInterface
    private interface StringSupplier {
        String get();
    }
}
