package com.claude.cameo.bridge.util;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;

import java.util.HashSet;
import java.util.Map;
import java.util.Set;

public final class JsonDiff {
    private JsonDiff() {
    }

    public static JsonObject diff(JsonElement before, JsonElement after, Set<String> ignorePaths, int maxChanges, boolean includeDetails) {
        JsonObject result = new JsonObject();
        JsonArray added = new JsonArray();
        JsonArray removed = new JsonArray();
        JsonArray changed = new JsonArray();
        JsonArray arrayLengthChanges = new JsonArray();
        Counter counter = new Counter(Math.max(1, maxChanges));
        compare("$", before, after, ignorePaths != null ? ignorePaths : Set.of(), includeDetails,
                counter, added, removed, changed, arrayLengthChanges);
        result.addProperty("truncated", counter.truncated);
        result.addProperty("changeCount", added.size() + removed.size() + changed.size() + arrayLengthChanges.size());
        result.add("added", added);
        result.add("removed", removed);
        result.add("changed", changed);
        result.add("arrayLengthChanges", arrayLengthChanges);
        return result;
    }

    public static Set<String> ignoreSet(JsonArray array) {
        Set<String> ignored = new HashSet<>();
        if (array != null) {
            for (JsonElement element : array) {
                if (element.isJsonPrimitive()) {
                    ignored.add(element.getAsString());
                }
            }
        }
        return ignored;
    }

    private static void compare(
            String path,
            JsonElement before,
            JsonElement after,
            Set<String> ignorePaths,
            boolean includeDetails,
            Counter counter,
            JsonArray added,
            JsonArray removed,
            JsonArray changed,
            JsonArray arrayLengthChanges) {
        if (counter.truncated || ignored(path, ignorePaths)) {
            return;
        }
        if (before == null || before.isJsonNull()) {
            if (after != null && !after.isJsonNull()) {
                addChange(added, path, null, after, includeDetails, counter);
            }
            return;
        }
        if (after == null || after.isJsonNull()) {
            addChange(removed, path, before, null, includeDetails, counter);
            return;
        }
        if (before.isJsonObject() && after.isJsonObject()) {
            JsonObject beforeObject = before.getAsJsonObject();
            JsonObject afterObject = after.getAsJsonObject();
            Set<String> keys = new HashSet<>();
            for (Map.Entry<String, JsonElement> entry : beforeObject.entrySet()) {
                keys.add(entry.getKey());
            }
            for (Map.Entry<String, JsonElement> entry : afterObject.entrySet()) {
                keys.add(entry.getKey());
            }
            keys.stream().sorted().forEach(key -> compare(
                    path + "." + key,
                    beforeObject.get(key),
                    afterObject.get(key),
                    ignorePaths,
                    includeDetails,
                    counter,
                    added,
                    removed,
                    changed,
                    arrayLengthChanges));
            return;
        }
        if (before.isJsonArray() && after.isJsonArray()) {
            JsonArray beforeArray = before.getAsJsonArray();
            JsonArray afterArray = after.getAsJsonArray();
            if (beforeArray.size() != afterArray.size()) {
                JsonObject entry = new JsonObject();
                entry.addProperty("path", path);
                entry.addProperty("beforeLength", beforeArray.size());
                entry.addProperty("afterLength", afterArray.size());
                addLimited(arrayLengthChanges, entry, counter);
            }
            int common = Math.min(beforeArray.size(), afterArray.size());
            for (int i = 0; i < common; i++) {
                compare(path + "[" + i + "]", beforeArray.get(i), afterArray.get(i), ignorePaths,
                        includeDetails, counter, added, removed, changed, arrayLengthChanges);
                if (counter.truncated) {
                    return;
                }
            }
            return;
        }
        if (!before.equals(after)) {
            addChange(changed, path, before, after, includeDetails, counter);
        }
    }

    private static boolean ignored(String path, Set<String> ignorePaths) {
        for (String ignored : ignorePaths) {
            if (path.equals(ignored) || path.startsWith(ignored)) {
                return true;
            }
        }
        return false;
    }

    private static void addChange(JsonArray target, String path, JsonElement before, JsonElement after, boolean includeDetails, Counter counter) {
        JsonObject entry = new JsonObject();
        entry.addProperty("path", path);
        if (includeDetails) {
            if (before != null) {
                entry.add("before", before.deepCopy());
            }
            if (after != null) {
                entry.add("after", after.deepCopy());
            }
        }
        addLimited(target, entry, counter);
    }

    private static void addLimited(JsonArray target, JsonObject entry, Counter counter) {
        if (counter.count >= counter.max) {
            counter.truncated = true;
            return;
        }
        target.add(entry);
        counter.count++;
    }

    private static final class Counter {
        private final int max;
        private int count = 0;
        private boolean truncated = false;

        private Counter(int max) {
            this.max = max;
        }
    }
}
