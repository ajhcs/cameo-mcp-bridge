package com.claude.cameo.bridge.util;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import org.junit.Test;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertTrue;

public class BridgeCapabilitiesTest {

    @Test
    public void buildStatusIncludesVersionAndCompatibilityMetadata() {
        JsonObject status = BridgeCapabilities.buildStatus(18740);

        assertEquals("ok", status.get("status").getAsString());
        assertEquals("CameoMCPBridge", status.get("plugin").getAsString());
        assertEquals("Cameo MCP Bridge", status.get("pluginName").getAsString());
        assertEquals("com.claude.cameo.bridge", status.get("pluginId").getAsString());
        assertEquals("1.0.0", status.get("version").getAsString());
        assertEquals("1.0.0", status.get("pluginVersion").getAsString());
        assertEquals("v1", status.get("apiVersion").getAsString());
        assertEquals("1", status.get("handshakeVersion").getAsString());
        assertTrue(status.get("healthy").getAsBoolean());

        JsonObject compatibility = status.getAsJsonObject("compatibility");
        assertNotNull(compatibility);
        assertTrue(compatibility.get("requiresExactPluginVersionMatch").getAsBoolean());
        assertEquals("1.0.0", compatibility.get("expectedPluginVersion").getAsString());

        JsonObject capabilities = status.getAsJsonObject("capabilities");
        assertNotNull(capabilities);
        assertTrue(capabilities.get("count").getAsInt() > 0);
        JsonArray endpoints = capabilities.getAsJsonArray("endpoints");
        assertNotNull(endpoints);
        assertTrue(endpoints.size() >= 10);
    }

    @Test
    public void buildCapabilitiesExposesKnownEndpointGroups() {
        JsonObject capabilities = BridgeCapabilities.buildCapabilities(18740);

        assertEquals("/api/v1/status", capabilities.get("statusEndpoint").getAsString());
        assertEquals("/api/v1/capabilities", capabilities.get("capabilitiesEndpoint").getAsString());

        JsonObject groups = capabilities.getAsJsonObject("capabilities").getAsJsonObject("groups");
        assertNotNull(groups);
        assertTrue(groups.has("health"));
        assertTrue(groups.has("diagrams"));
        assertTrue(groups.has("elements"));
        JsonArray endpoints = capabilities.getAsJsonObject("capabilities").getAsJsonArray("endpoints");
        assertTrue(
                endpoints.toString().contains("cameo_get_shape_properties")
                        && endpoints.toString().contains("cameo_route_paths")
                        && endpoints.toString().contains("cameo_reparent_shapes")
                        && endpoints.toString().contains("cameo_set_usecase_subject"));
    }
}
