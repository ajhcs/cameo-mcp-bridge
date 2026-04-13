# MCP Contract Hardening Minor Release

Date: 2026-04-13
Release: `2.1.0`

## Summary

This minor release hardens the bridge around the exact failure modes that showed up in live Cameo work: camelCase vs snake_case MCP argument mismatches, oversized diagram payloads that blow past client token limits, and a risky `ActivityPartition` fallback path that could rebuild an existing swimlane container.

Version `2.1.0` does not change the API family or handshake version. It makes the current `v1` surface safer and easier to drive from real MCP clients.

## Shipped

### 1. More forgiving MCP argument handling

- Added argument aliases for the common camelCase forms emitted by MCP clients
- Covered the problematic diagram, relationship, containment, and query calls that previously failed validation
- Corrected `cameo_query_elements` so owner/root/package aliases map to the actual element-ID scope used by the Java bridge

### 2. Token-safe diagram inspection

- `cameo_get_diagram_image` can now return metadata only with `include_image=false`
- Diagram images can now be resized before returning to the MCP client with `max_width` / `max_height`
- Diagram images can now be transcoded to `jpeg` or `webp` for smaller payloads
- `cameo_list_diagram_shapes` now supports paging, filtering, nested-parent filtering, and summary-only responses

### 3. Safer activity swimlane fallback

- Fixed the Groovy fallback to use integer rectangle dimensions when reshaping swimlanes
- Stopped the fallback from deleting and recreating an existing swimlane container when the partition presentation cannot be resolved safely
- Kept the existing fallback path in place for new swimlane creation, while making it fail closed instead of destructively

### 4. Regression coverage

- Added tests for MCP alias handling on the affected tools
- Added tests for image omission, resize/transcode, and shape-summary behavior
- Added tests that pin the non-destructive `ActivityPartition` fallback behavior

## Change Notes

- `cameo_get_diagram_image` is no longer effectively all-or-nothing for large diagrams
- `cameo_list_diagram_shapes` is now usable on large diagrams without dumping the full shape tree into the client context
- Clients that accidentally send `diagramId`, `elementId`, `parentId`, or `ownerId` to the affected Python tools should now resolve cleanly instead of failing validation
- The bridge still does not provide first-class file-path export for diagrams; macros remain the fallback when the user needs a file written directly to disk

## Compatibility

- Python MCP server version: `2.1.0`
- Plugin version: `2.1.0`
- API version: `v1`
- Handshake version: `1`

Plugin/server version lockstep is still required.

## Follow-on Work

- Replace the temporary `ActivityPartition` macro fallback with a dedicated Java-native swimlane endpoint
- Consider strict rejection of unknown MCP tool fields so bad client calls fail explicitly instead of being partially ignored
- Add equivalent token-safe shaping controls to any other read endpoints that can return large nested payloads
