package com.nomagic.magicdraw.mcpbridge.util;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonPrimitive;
import com.nomagic.magicdraw.core.Project;
import com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Enumeration;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.EnumerationLiteral;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Property;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Type;
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Stereotype;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;

/**
 * Type-aware coercion for stereotype tagged values.
 *
 * <p>The generic JSON coercion path is sufficient for primitives and element
 * references, but stereotype enum tags require an actual EnumerationLiteral.
 * This helper resolves those literals by ID or name before values are passed
 * into Cameo's stereotype-property setter.</p>
 */
public final class TaggedValueCoercion {

    private TaggedValueCoercion() {
    }

    public static Object coerceForTag(
            Project project,
            Stereotype stereotype,
            String tagName,
            JsonElement value) {
        Property tagDefinition = findTagDefinition(stereotype, tagName);
        if (tagDefinition == null) {
            return coerceGeneric(project, value);
        }
        return coerceForType(project, tagDefinition.getType(), value, stereotype, tagName);
    }

    private static Property findTagDefinition(Stereotype stereotype, String tagName) {
        List<Property> attributes = stereotype.getAttribute();
        if (attributes == null) {
            return null;
        }
        for (Property attribute : attributes) {
            if (attribute == null || StereotypesHelper.isExtensionProperty(attribute)) {
                continue;
            }
            if (tagName.equals(attribute.getName())) {
                return attribute;
            }
        }
        return null;
    }

    private static Object coerceForType(
            Project project,
            Type expectedType,
            JsonElement value,
            Stereotype stereotype,
            String tagName) {
        if (value == null || value.isJsonNull()) {
            return null;
        }
        if (value.isJsonArray()) {
            JsonArray array = value.getAsJsonArray();
            List<Object> converted = new ArrayList<>(array.size());
            for (JsonElement item : array) {
                converted.add(coerceForType(project, expectedType, item, stereotype, tagName));
            }
            return converted;
        }
        if (expectedType instanceof Enumeration) {
            return resolveEnumerationLiteral(
                    project,
                    (Enumeration) expectedType,
                    value,
                    stereotype,
                    tagName);
        }
        return coerceGeneric(project, value);
    }

    private static EnumerationLiteral resolveEnumerationLiteral(
            Project project,
            Enumeration enumeration,
            JsonElement value,
            Stereotype stereotype,
            String tagName) {
        EnumerationLiteral byId = resolveEnumerationLiteralById(project, enumeration, value);
        if (byId != null) {
            return byId;
        }

        String candidate = extractLiteralCandidate(value);
        if (candidate != null) {
            for (EnumerationLiteral literal : safeOwnedLiterals(enumeration)) {
                if (literal == null) {
                    continue;
                }
                String literalName = literal.getName();
                if (candidate.equals(literal.getID())
                        || (literalName != null && candidate.equals(literalName))
                        || (literalName != null && candidate.equalsIgnoreCase(literalName))) {
                    return literal;
                }
            }
        }

        throw new IllegalArgumentException(
                "Enumeration \"" + stereotype.getQualifiedName() + "::" + tagName
                        + "\" does not own literal \"" + value + "\".");
    }

    private static EnumerationLiteral resolveEnumerationLiteralById(
            Project project,
            Enumeration enumeration,
            JsonElement value) {
        if (!value.isJsonObject()) {
            return null;
        }
        JsonObject object = value.getAsJsonObject();
        if (!object.has("id") || !object.get("id").isJsonPrimitive()) {
            return null;
        }

        String id = object.get("id").getAsString();
        Element referenced = (Element) project.getElementByID(id);
        if (!(referenced instanceof EnumerationLiteral)) {
            return null;
        }

        EnumerationLiteral literal = (EnumerationLiteral) referenced;
        for (EnumerationLiteral owned : safeOwnedLiterals(enumeration)) {
            if (owned != null && id.equals(owned.getID())) {
                return literal;
            }
        }
        return null;
    }

    private static Collection<EnumerationLiteral> safeOwnedLiterals(Enumeration enumeration) {
        Collection<EnumerationLiteral> owned = enumeration.getOwnedLiteral();
        return owned != null ? owned : List.of();
    }

    private static String extractLiteralCandidate(JsonElement value) {
        if (value == null || value.isJsonNull()) {
            return null;
        }
        if (value.isJsonPrimitive() && value.getAsJsonPrimitive().isString()) {
            String candidate = value.getAsString();
            return candidate == null || candidate.isEmpty() ? null : candidate;
        }
        if (!value.isJsonObject()) {
            return null;
        }
        JsonObject object = value.getAsJsonObject();
        String[] keys = new String[]{"name", "literal", "value"};
        for (String key : keys) {
            if (object.has(key) && object.get(key).isJsonPrimitive()) {
                JsonPrimitive primitive = object.getAsJsonPrimitive(key);
                if (primitive.isString()) {
                    String candidate = primitive.getAsString();
                    if (candidate != null && !candidate.isEmpty()) {
                        return candidate;
                    }
                }
            }
        }
        return null;
    }

    private static Object coerceGeneric(Project project, JsonElement value) {
        if (value == null || value.isJsonNull()) {
            return null;
        }
        if (value.isJsonArray()) {
            JsonArray array = value.getAsJsonArray();
            List<Object> converted = new ArrayList<>(array.size());
            for (JsonElement item : array) {
                converted.add(coerceGeneric(project, item));
            }
            return converted;
        }
        if (value.isJsonObject()) {
            JsonObject object = value.getAsJsonObject();
            if (object.has("id") && object.get("id").isJsonPrimitive()) {
                String id = object.get("id").getAsString();
                Element referenced = (Element) project.getElementByID(id);
                if (referenced != null) {
                    return referenced;
                }
            }
            return object.toString();
        }

        JsonPrimitive primitive = value.getAsJsonPrimitive();
        if (primitive.isBoolean()) {
            return primitive.getAsBoolean();
        }
        if (primitive.isNumber()) {
            return primitive.getAsNumber();
        }
        return primitive.getAsString();
    }
}
