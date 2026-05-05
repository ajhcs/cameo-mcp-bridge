package com.claude.cameo.bridge.util;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.nomagic.magicdraw.core.Application;
import com.nomagic.magicdraw.core.Project;

import java.io.File;
import java.net.URL;
import java.security.CodeSource;
import java.util.LinkedHashSet;
import java.util.Locale;
import java.util.Set;

/**
 * Shared diagnostics for optional CATIA Magic product integrations.
 */
public final class OptionalCapabilitySupport {

    private OptionalCapabilitySupport() {
    }

    public static JsonObject baseCapabilities(String family, String mode) {
        JsonObject json = new JsonObject();
        json.addProperty("family", family);
        json.addProperty("mode", mode);
        json.add("projectState", projectState());
        return json;
    }

    public static JsonObject projectState() {
        JsonObject state = new JsonObject();
        Project project = Application.getInstance().getProject();
        state.addProperty("open", project != null);
        if (project != null) {
            state.addProperty("name", safe(project.getName()));
            state.addProperty("filePath", safe(project.getFileName()));
            state.addProperty("remote", project.isRemote());
            state.addProperty("dirty", project.isDirty());
        }
        return state;
    }

    public static JsonObject classProbe(String... classNames) {
        JsonObject probe = new JsonObject();
        JsonArray found = new JsonArray();
        JsonArray missing = new JsonArray();
        JsonArray details = new JsonArray();

        for (String className : classNames) {
            JsonObject detail = new JsonObject();
            detail.addProperty("className", className);
            try {
                Class<?> cls = loadClass(className);
                detail.addProperty("found", true);
                detail.addProperty("loadedName", cls.getName());
                detail.addProperty("codeSource", codeSource(cls));
                found.add(className);
            } catch (ClassNotFoundException | LinkageError | SecurityException e) {
                detail.addProperty("found", false);
                detail.addProperty("errorType", e.getClass().getName());
                detail.addProperty("message", safe(e.getMessage()));
                missing.add(className);
            }
            details.add(detail);
        }

        probe.addProperty("allFound", missing.size() == 0);
        probe.add("classesFound", found);
        probe.add("classesMissing", missing);
        probe.add("classes", details);
        return probe;
    }

    public static Class<?> loadClass(String className) throws ClassNotFoundException {
        Set<ClassLoader> loaders = new LinkedHashSet<>();
        loaders.add(Thread.currentThread().getContextClassLoader());
        loaders.add(OptionalCapabilitySupport.class.getClassLoader());
        loaders.add(Application.class.getClassLoader());
        loaders.add(ClassLoader.getSystemClassLoader());

        ClassNotFoundException last = null;
        for (ClassLoader loader : loaders) {
            if (loader == null) {
                continue;
            }
            try {
                return Class.forName(className, false, loader);
            } catch (ClassNotFoundException e) {
                last = e;
            }
        }

        try {
            return Class.forName(className);
        } catch (ClassNotFoundException e) {
            if (last != null) {
                e.addSuppressed(last);
            }
            throw e;
        }
    }

    public static JsonArray pluginDirectories(String... names) {
        JsonArray array = new JsonArray();
        File plugins = new File(inferInstallRoot(), "plugins");
        if (!plugins.isDirectory()) {
            return array;
        }
        File[] children = plugins.listFiles(File::isDirectory);
        if (children == null) {
            return array;
        }
        for (File child : children) {
            String lower = child.getName().toLowerCase(Locale.ROOT);
            for (String name : names) {
                if (lower.contains(name.toLowerCase(Locale.ROOT))) {
                    JsonObject entry = new JsonObject();
                    entry.addProperty("name", child.getName());
                    entry.addProperty("path", child.getAbsolutePath());
                    array.add(entry);
                    break;
                }
            }
        }
        return array;
    }

    public static JsonObject unsupported(String family, String reason, String nextAction) {
        JsonObject json = baseCapabilities(family, "unsupported");
        json.addProperty("available", false);
        json.addProperty("status", "unsupported");
        json.addProperty("reason", reason);
        json.addProperty("nextAction", nextAction);
        return json;
    }

    public static JsonObject previewAccepted(String family, JsonObject request, String message) {
        JsonObject json = new JsonObject();
        json.addProperty("family", family);
        json.addProperty("preview", true);
        json.addProperty("writePerformed", false);
        json.addProperty("message", message);
        json.add("request", request);
        json.add("projectState", projectState());
        return json;
    }

    public static String safe(String value) {
        return value == null ? "" : value;
    }

    private static String codeSource(Class<?> cls) {
        try {
            CodeSource source = cls.getProtectionDomain().getCodeSource();
            if (source == null) {
                return "";
            }
            URL location = source.getLocation();
            return location != null ? location.toString() : "";
        } catch (SecurityException e) {
            return "";
        }
    }

    private static File inferInstallRoot() {
        String explicit = System.getProperty("cameo.home");
        if (explicit == null || explicit.isEmpty()) {
            explicit = System.getProperty("md.home");
        }
        if (explicit == null || explicit.isEmpty()) {
            explicit = System.getProperty("user.dir", ".");
        }
        return new File(explicit);
    }
}
