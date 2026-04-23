package com.claude.cameo.bridge.util;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class CompartmentAliasResolver {

    private CompartmentAliasResolver() {
    }

    public static List<String> candidatePropertyNames(String requestedKey) {
        String normalized = normalizeKey(requestedKey);
        if (normalized.startsWith("show") && normalized.length() > 4) {
            normalized = normalized.substring(4);
        } else if (normalized.startsWith("suppress") && normalized.length() > 8) {
            normalized = normalized.substring(8);
        }

        Map<String, String[]> aliases = new LinkedHashMap<>();
        aliases.put("properties", new String[]{"Suppress Properties", "Show Properties"});
        aliases.put("operations", new String[]{"Show Operations", "Suppress Operations"});
        aliases.put("constraints", new String[]{"Suppress Constraints", "Show Constraints"});
        aliases.put("taggedvalues", new String[]{"Show Tagged Values"});
        aliases.put("ports", new String[]{"Suppress Ports", "Show Ports"});
        aliases.put("attributes", new String[]{"Suppress Attributes"});
        aliases.put("fullports", new String[]{"Suppress Full Ports", "Show Full Ports"});
        aliases.put("parts", new String[]{"Suppress Parts", "Show Parts"});
        aliases.put("content", new String[]{"Suppress Content", "Show Content"});
        aliases.put("references", new String[]{"Suppress References", "Show References"});
        aliases.put("values", new String[]{"Suppress Values", "Show Values"});
        aliases.put("flowproperties", new String[]{"Suppress Flow Properties", "Show Flow Properties"});
        aliases.put("proxyports", new String[]{"Suppress Proxy Ports", "Show Proxy Ports"});
        aliases.put("behaviors", new String[]{"Suppress Behaviors", "Show Behaviors"});
        aliases.put("receptions", new String[]{"Suppress Receptions", "Show Receptions"});
        aliases.put("structure", new String[]{"Suppress Structure", "Show Structure"});
        aliases.put("stereotype", new String[]{"Show Stereotype"});
        aliases.put("name", new String[]{"Show Name"});
        aliases.put("type", new String[]{"Show Type"});

        String[] candidates = aliases.get(normalized);
        if (candidates == null) {
            return List.of();
        }
        return List.of(candidates);
    }

    private static String normalizeKey(String value) {
        return value == null ? "" : value.replaceAll("[^A-Za-z0-9]", "").toLowerCase();
    }
}
