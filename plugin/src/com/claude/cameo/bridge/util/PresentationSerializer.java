package com.claude.cameo.bridge.util;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.nomagic.magicdraw.properties.PropertyManager;
import com.nomagic.magicdraw.uml.symbols.DiagramPresentationElement;
import com.nomagic.magicdraw.uml.symbols.PresentationElement;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Diagram;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement;

import java.awt.Rectangle;
import java.util.ArrayList;
import java.util.Collection;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class PresentationSerializer {

    private PresentationSerializer() {
    }

    public static JsonObject diagramSummary(DiagramPresentationElement dpe) {
        JsonObject json = new JsonObject();
        if (dpe == null) {
            return json;
        }
        Diagram diagram = dpe.getDiagram();
        if (diagram != null) {
            json.addProperty("id", diagram.getID());
        }
        json.addProperty("name", dpe.getName() != null ? dpe.getName() : "");
        json.addProperty("type", dpe.getDiagramType() != null ? dpe.getDiagramType().getType() : "");
        if (diagram != null && diagram.getOwner() != null) {
            json.add("owner", ElementSerializer.toJsonCompact(diagram.getOwner()));
        }
        return json;
    }

    public static JsonObject presentationSummary(PresentationElement pe, String parentPresentationId) {
        JsonObject json = new JsonObject();
        if (pe == null) {
            return json;
        }
        json.addProperty("presentationId", pe.getID());
        json.addProperty("presentationClassName", pe.getClass().getName());
        json.addProperty("shapeType", pe.getClass().getSimpleName());
        if (parentPresentationId != null) {
            json.addProperty("parentPresentationId", parentPresentationId);
        }

        try {
            Element element = pe.getElement();
            if (element != null) {
                json.add("element", ElementSerializer.toJsonCompact(element));
                json.addProperty("elementId", element.getID());
                if (element instanceof NamedElement) {
                    json.addProperty("elementName", ((NamedElement) element).getName());
                }
            }
        } catch (Exception e) {
            json.addProperty("elementWarning", e.getMessage());
        }

        try {
            Rectangle bounds = pe.getBounds();
            if (bounds != null) {
                JsonObject boundsJson = new JsonObject();
                boundsJson.addProperty("x", bounds.x);
                boundsJson.addProperty("y", bounds.y);
                boundsJson.addProperty("width", bounds.width);
                boundsJson.addProperty("height", bounds.height);
                json.add("bounds", boundsJson);
            }
        } catch (Exception e) {
            json.addProperty("boundsWarning", e.getMessage());
        }

        List<PresentationElement> children = pe.getPresentationElements();
        json.addProperty("childCount", children != null ? children.size() : 0);
        return json;
    }

    public static JsonObject presentationWithProperties(
            PresentationElement pe,
            String parentPresentationId,
            boolean includeRaw,
            boolean summaryOnly) {
        JsonObject json = presentationSummary(pe, parentPresentationId);
        try {
            PropertyManager manager = pe.getPropertyManager();
            json.add("propertyManager", PropertySerializer.serializeManager(manager, includeRaw, summaryOnly));
        } catch (Exception e) {
            JsonArray warnings = new JsonArray();
            warnings.add("Could not read presentation property manager: " + e.getMessage());
            json.add("warnings", warnings);
        }
        JsonArray children = new JsonArray();
        List<PresentationElement> childElements = pe.getPresentationElements();
        if (childElements != null) {
            for (PresentationElement child : childElements) {
                children.add(presentationSummary(child, pe.getID()));
            }
        }
        json.add("children", children);
        return json;
    }

    public static List<PresentationElement> flatten(DiagramPresentationElement dpe, Map<String, String> parentById) {
        List<PresentationElement> flattened = new ArrayList<>();
        if (dpe != null) {
            collect(dpe.getPresentationElements(), flattened, parentById, null);
        }
        return flattened;
    }

    public static JsonArray summarizePresentations(Collection<PresentationElement> elements, Map<String, String> parentById) {
        JsonArray array = new JsonArray();
        if (elements != null) {
            for (PresentationElement pe : elements) {
                array.add(presentationSummary(pe, parentById != null ? parentById.get(pe.getID()) : null));
            }
        }
        return array;
    }

    public static JsonObject countByType(Collection<PresentationElement> elements) {
        JsonObject counts = new JsonObject();
        if (elements != null) {
            Map<String, Integer> map = new LinkedHashMap<>();
            for (PresentationElement pe : elements) {
                String type = pe != null ? pe.getClass().getSimpleName() : "null";
                map.put(type, map.getOrDefault(type, 0) + 1);
            }
            for (Map.Entry<String, Integer> entry : map.entrySet()) {
                counts.addProperty(entry.getKey(), entry.getValue());
            }
        }
        return counts;
    }

    public static PresentationElement findById(DiagramPresentationElement dpe, String presentationId) {
        if (presentationId == null) {
            return null;
        }
        for (PresentationElement pe : flatten(dpe, null)) {
            if (presentationId.equals(pe.getID())) {
                return pe;
            }
        }
        return null;
    }

    private static void collect(
            List<PresentationElement> elements,
            List<PresentationElement> sink,
            Map<String, String> parentById,
            String parentPresentationId) {
        if (elements == null) {
            return;
        }
        for (PresentationElement pe : elements) {
            sink.add(pe);
            if (parentById != null && parentPresentationId != null) {
                parentById.put(pe.getID(), parentPresentationId);
            }
            collect(pe.getPresentationElements(), sink, parentById, pe.getID());
        }
    }
}
