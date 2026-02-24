package com.claude.cameo.bridge;

import com.nomagic.magicdraw.plugins.Plugin;

public class CameoMCPBridgePlugin extends Plugin {
    @Override
    public void init() {
    }

    @Override
    public boolean close() {
        return true;
    }

    @Override
    public boolean isSupported() {
        return true;
    }
}
