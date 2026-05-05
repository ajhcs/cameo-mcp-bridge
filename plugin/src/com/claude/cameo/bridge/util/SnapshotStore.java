package com.claude.cameo.bridge.util;

import com.google.gson.JsonObject;

import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public final class SnapshotStore {
    private static final Map<String, JsonObject> SNAPSHOTS = new LinkedHashMap<>();

    private SnapshotStore() {
    }

    public static synchronized JsonObject create(JsonObject snapshot) {
        String id = UUID.randomUUID().toString();
        snapshot.addProperty("snapshotId", id);
        snapshot.addProperty("createdAt", Instant.now().toString());
        SNAPSHOTS.put(id, snapshot);
        return snapshot.deepCopy();
    }

    public static synchronized List<JsonObject> list() {
        List<JsonObject> snapshots = new ArrayList<>();
        for (JsonObject snapshot : SNAPSHOTS.values()) {
            JsonObject summary = new JsonObject();
            copyIfPresent(snapshot, summary, "snapshotId");
            copyIfPresent(snapshot, summary, "createdAt");
            copyIfPresent(snapshot, summary, "name");
            copyIfPresent(snapshot, summary, "target");
            copyIfPresent(snapshot, summary, "summary");
            snapshots.add(summary);
        }
        return snapshots;
    }

    public static synchronized JsonObject get(String id) {
        JsonObject snapshot = SNAPSHOTS.get(id);
        return snapshot != null ? snapshot.deepCopy() : null;
    }

    public static synchronized boolean delete(String id) {
        return SNAPSHOTS.remove(id) != null;
    }

    private static void copyIfPresent(JsonObject source, JsonObject target, String key) {
        if (source.has(key)) {
            target.add(key, source.get(key).deepCopy());
        }
    }
}
