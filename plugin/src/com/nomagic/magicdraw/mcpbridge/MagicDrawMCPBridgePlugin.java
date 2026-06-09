package com.nomagic.magicdraw.mcpbridge;

import com.nomagic.magicdraw.plugins.Plugin;
import com.nomagic.magicdraw.core.Application;
import java.util.logging.Logger;

public class MagicDrawMCPBridgePlugin extends Plugin {

    private static final Logger LOG = Logger.getLogger(MagicDrawMCPBridgePlugin.class.getName());
    private HttpBridgeServer server;

    @Override
    public void init() {
        int port = Integer.parseInt(System.getProperty("cameo.mcp.port", "18740"));
        try {
            server = new HttpBridgeServer(port);
            server.start();
            Application.getInstance().getGUILog().log(
                "CameoMCPBridge: HTTP server started on port " + port);
            LOG.info("CameoMCPBridge: HTTP server started on port " + port);
        } catch (Exception e) {
            LOG.severe("CameoMCPBridge: Failed to start HTTP server: " + e.getMessage());
            Application.getInstance().getGUILog().showError(
                "CameoMCPBridge: Failed to start HTTP server: " + e.getMessage());
        }
    }

    @Override
    public boolean close() {
        if (server != null) {
            server.stop();
            LOG.info("CameoMCPBridge: HTTP server stopped");
        }
        return true;
    }

    @Override
    public boolean isSupported() {
        return true;
    }
}
