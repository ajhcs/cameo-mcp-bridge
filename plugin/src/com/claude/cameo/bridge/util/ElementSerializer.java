package com.claude.cameo.bridge.util;

import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Comment;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Classifier;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Parameter;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Property;
import com.nomagic.uml2.ext.magicdraw.activities.mdbasicactivities.ActivityParameterNode;
import com.nomagic.uml2.ext.magicdraw.compositestructures.mdinternalstructures.Connector;
import com.nomagic.uml2.ext.magicdraw.compositestructures.mdinternalstructures.ConnectorEnd;
import com.nomagic.uml2.ext.magicdraw.compositestructures.mdinternalstructures.ConnectableElement;
import com.nomagic.uml2.ext.magicdraw.auxiliaryconstructs.mdinformationflows.InformationFlow;
import com.nomagic.uml2.ext.magicdraw.mdprofiles.Stereotype;
import com.nomagic.uml2.ext.jmi.helpers.StereotypesHelper;
import com.nomagic.magicdraw.uml.ClassTypes;
import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonPrimitive;
import java.lang.reflect.Method;
import java.util.Collection;
import java.util.List;
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Converts Cameo model {@link Element} objects into JSON representations
 * suitable for the bridge REST API.
 * <p>
 * Produces a standard envelope with id, type, name, owner, stereotypes,
 * documentation, and tagged values for any element.
 */
public class ElementSerializer {
    private static final Logger LOG = Logger.getLogger(ElementSerializer.class.getName());

    /**
     * Serialize an element to a JSON object with full detail.
     * <p>
     * The resulting object includes:
     * <ul>
     *   <li>{@code id} - the element ID</li>
     *   <li>{@code type} - the metaclass short name (e.g. "Class", "Package")</li>
     *   <li>{@code humanType} - the human-readable type name</li>
     *   <li>{@code name} - the element name (if it is a NamedElement)</li>
     *   <li>{@code ownerId} - the ID of the owning element</li>
     *   <li>{@code stereotypes} - array of applied stereotype names</li>
     *   <li>{@code documentation} - concatenated body text of owned comments</li>
     *   <li>{@code taggedValues} - object mapping tag name to serialized value</li>
     *   <li>{@code childCount} - number of directly owned elements</li>
     * </ul>
     *
     * @param element the Cameo model element
     * @return a JsonObject representation
     */
    public static JsonObject toJson(Element element) {
        JsonObject json = toJsonReference(element);

        // Documentation (from owned comments)
        try {
            Collection<Comment> comments = element.getOwnedComment();
            if (comments != null && !comments.isEmpty()) {
                StringBuilder doc = new StringBuilder();
                for (Comment c : comments) {
                    String body = c.getBody();
                    if (body != null && !body.isEmpty()) {
                        if (doc.length() > 0) {
                            doc.append("\n");
                        }
                        doc.append(body);
                    }
                }
                if (doc.length() > 0) {
                    json.addProperty("documentation", doc.toString());
                }
            }
        } catch (Exception e) {
            LOG.log(Level.FINE, "Could not read comments for " + element.getID(), e);
        }

        // Tagged values from all applied stereotypes
        try {
            List<Stereotype> stereotypes = StereotypesHelper.getStereotypes(element);
            if (stereotypes != null && !stereotypes.isEmpty()) {
                JsonObject tags = new JsonObject();
                for (Stereotype st : stereotypes) {
                    List<Property> properties = st.getAttribute();
                    if (properties != null) {
                        for (Property prop : properties) {
                            // Skip extension meta-properties (base_Class, etc.)
                            if (StereotypesHelper.isExtensionProperty(prop)) {
                                continue;
                            }
                            String tagName = prop.getName();
                            if (tagName == null || tagName.isEmpty()) {
                                continue;
                            }
                            try {
                                Object val = StereotypesHelper.getStereotypePropertyFirst(element, st, tagName);
                                if (val != null) {
                                    JsonElement serialized = serializeTaggedValue(val);
                                    if (serialized != null) {
                                        tags.add(tagName, serialized);
                                    }
                                }
                            } catch (Exception e) {
                                LOG.log(Level.FINE, "Could not read tag " + tagName, e);
                            }
                        }
                    }
                }
                if (tags.size() > 0) {
                    json.add("taggedValues", tags);
                }
            }
        } catch (Exception e) {
            LOG.log(Level.FINE, "Could not read tagged values for " + element.getID(), e);
        }

        // Structured readback for information and item flows.
        if (element instanceof InformationFlow) {
            appendInformationFlowFields(json, (InformationFlow) element, true);
        }

        if (element instanceof Connector) {
            appendConnectorFields(json, (Connector) element);
        }

        // Child count
        try {
            Collection<Element> children = element.getOwnedElement();
            json.addProperty("childCount", children != null ? children.size() : 0);
        } catch (Exception e) {
            json.addProperty("childCount", 0);
        }

        return json;
    }

    /**
     * Serialize an element with minimal detail (id, type, name only).
     * Useful for listing children or search results where full detail is excessive.
     *
     * @param element the Cameo model element
     * @return a compact JsonObject representation
     */
    public static JsonObject toJsonCompact(Element element) {
        JsonObject json = toJsonShallow(element);
        appendOwnerFields(json, element.getOwner());
        appendTypedElementFields(json, element);
        return json;
    }

    public static JsonObject toJsonReference(Element element) {
        JsonObject json = toJsonCompact(element);
        appendQualifiedName(json, element);
        appendStereotypeNames(json, element);
        appendMultiplicityFields(json, element);
        appendPropertyLikeFields(json, element);
        appendPortLikeFields(json, element);
        appendParameterLikeFields(json, element);

        if (element instanceof InformationFlow) {
            appendInformationFlowFields(json, (InformationFlow) element, false);
        } else if (element instanceof Connector) {
            json.addProperty("endCount", safeSize(((Connector) element).getEnd()));
        }

        return json;
    }

    public static JsonObject toJsonConnectorEnd(ConnectorEnd end) {
        JsonObject json = new JsonObject();
        if (end == null) {
            return json;
        }

        ConnectableElement role = end.getRole();
        if (role != null) {
            json.add("role", toJsonReference(role));
        }

        Property partWithPort = end.getPartWithPort();
        if (partWithPort != null) {
            json.add("partWithPort", toJsonReference(partWithPort));
        }

        Object definingEnd = invokeZeroArg(end, "getDefiningEnd");
        if (definingEnd instanceof Element) {
            json.add("definingEnd", toJsonCompact((Element) definingEnd));
        }

        return json;
    }

    public static JsonArray toJsonReferenceArray(Collection<? extends Element> elements) {
        JsonArray array = new JsonArray();
        if (elements == null) {
            return array;
        }
        for (Element element : elements) {
            if (element != null) {
                array.add(toJsonReference(element));
            }
        }
        return array;
    }

    public static Stereotype getFlowPropertyStereotype(Element element) {
        try {
            Stereotype flowProperty = StereotypesHelper.getAppliedStereotypeByString(
                    element,
                    "FlowProperty");
            if (flowProperty == null) {
                flowProperty = StereotypesHelper.getAppliedStereotypeByString(
                        element,
                        "flowProperty");
            }
            return flowProperty;
        } catch (Exception e) {
            LOG.log(Level.FINE, "Could not resolve flow property stereotype for " + safeId(element), e);
            return null;
        }
    }

    public static String readFlowPropertyDirection(Property property, Stereotype flowPropertyStereo) {
        if (property == null || flowPropertyStereo == null) {
            return null;
        }
        try {
            Object direction = StereotypesHelper.getStereotypePropertyFirst(
                    property,
                    flowPropertyStereo,
                    "direction");
            return stringifyEnumLike(direction);
        } catch (Exception e) {
            LOG.log(Level.FINE, "Could not read flow property direction for " + property.getID(), e);
            return null;
        }
    }

    private static JsonObject toJsonShallow(Element element) {
        JsonObject json = new JsonObject();
        json.addProperty("id", element.getID());

        try {
            String shortName = ClassTypes.getShortName(element.getClassType());
            json.addProperty("type", shortName != null ? shortName : element.getClassType().getSimpleName());
        } catch (Exception e) {
            json.addProperty("type", element.getHumanType());
        }

        json.addProperty("humanType", element.getHumanType());

        if (element instanceof NamedElement) {
            String name = ((NamedElement) element).getName();
            json.addProperty("name", name != null ? name : "");
        }

        return json;
    }

    private static void appendInformationFlowFields(
            JsonObject json,
            InformationFlow informationFlow,
            boolean includeRealizingConnectorDetails) {
        try {
            json.add("informationSources", toJsonReferenceArray(informationFlow.getInformationSource()));
            json.add("informationTargets", toJsonReferenceArray(informationFlow.getInformationTarget()));
            json.add("conveyed", toJsonReferenceArray(informationFlow.getConveyed()));
            json.add("realizingConnectors", toJsonReferenceArray(informationFlow.getRealizingConnector()));

            Stereotype itemFlow = StereotypesHelper.getAppliedStereotypeByString(
                    informationFlow,
                    "ItemFlow");
            if (itemFlow != null) {
                Object itemProperty = StereotypesHelper.getStereotypePropertyFirst(
                        informationFlow,
                        itemFlow,
                        "itemProperty");
                if (itemProperty instanceof Element) {
                    json.add("itemProperty", toJsonReference((Element) itemProperty));
                }
            }

            if (includeRealizingConnectorDetails) {
                JsonArray details = new JsonArray();
                for (Connector connector : informationFlow.getRealizingConnector()) {
                    if (connector == null) {
                        continue;
                    }
                    JsonObject connectorJson = toJsonReference(connector);
                    appendConnectorFields(connectorJson, connector);
                    details.add(connectorJson);
                }
                if (details.size() > 0) {
                    json.add("realizingConnectorDetails", details);
                }
            }
        } catch (Exception e) {
            LOG.log(Level.FINE,
                    "Could not read structured information flow fields for " + informationFlow.getID(),
                    e);
        }
    }

    private static void appendConnectorFields(JsonObject json, Connector connector) {
        try {
            JsonArray connectorEnds = new JsonArray();
            Collection<ConnectorEnd> ends = connector.getEnd();
            if (ends != null) {
                for (ConnectorEnd end : ends) {
                    if (end != null) {
                        connectorEnds.add(toJsonConnectorEnd(end));
                    }
                }
            }
            if (connectorEnds.size() > 0) {
                json.add("connectorEnds", connectorEnds);
            }
            json.addProperty("endCount", connectorEnds.size());
        } catch (Exception e) {
            LOG.log(Level.FINE, "Could not read connector ends for " + connector.getID(), e);
        }
    }

    private static void appendQualifiedName(JsonObject json, Element element) {
        if (!(element instanceof NamedElement)) {
            return;
        }
        try {
            String qualifiedName = ((NamedElement) element).getQualifiedName();
            if (qualifiedName != null && !qualifiedName.trim().isEmpty()) {
                json.addProperty("qualifiedName", qualifiedName);
            }
        } catch (Exception e) {
            LOG.log(Level.FINE, "Could not read qualified name for " + element.getID(), e);
        }
    }

    private static void appendOwnerFields(JsonObject json, Element owner) {
        if (owner == null) {
            return;
        }
        json.addProperty("ownerId", owner.getID());
        if (owner instanceof NamedElement) {
            String ownerName = ((NamedElement) owner).getName();
            if (ownerName != null && !ownerName.isEmpty()) {
                json.addProperty("ownerName", ownerName);
            }
        }
        String ownerType = owner.getHumanType();
        if (ownerType != null && !ownerType.isEmpty()) {
            json.addProperty("ownerType", ownerType);
        }
    }

    private static void appendTypedElementFields(JsonObject json, Object typedElement) {
        Object type = invokeZeroArg(typedElement, "getType");
        if (!(type instanceof Element)) {
            return;
        }
        Element typeElement = (Element) type;
        json.addProperty("typeId", typeElement.getID());
        if (typeElement instanceof NamedElement) {
            String typeName = ((NamedElement) typeElement).getName();
            if (typeName != null && !typeName.isEmpty()) {
                json.addProperty("typeName", typeName);
            }
        }
        json.add("typeRef", toJsonShallow(typeElement));
    }

    private static void appendMultiplicityFields(JsonObject json, Object element) {
        appendIntegerProperty(json, "lower", invokeIntegerZeroArg(element, "getLower"));
        appendIntegerProperty(json, "upper", invokeIntegerZeroArg(element, "getUpper"));
        appendBooleanProperty(json, "isOrdered", invokeBooleanZeroArg(element, "isOrdered"));
        appendBooleanProperty(json, "isUnique", invokeBooleanZeroArg(element, "isUnique"));
        appendBooleanProperty(json, "isMultivalued", invokeBooleanZeroArg(element, "isMultivalued"));
    }

    private static void appendPropertyLikeFields(JsonObject json, Element element) {
        appendTypedElementFields(json, element);
        if (!(element instanceof Property)) {
            return;
        }

        Property property = (Property) element;

        Element association = property.getAssociation();
        if (association != null) {
            json.add("association", toJsonCompact(association));
        }

        String aggregation = stringifyEnumLike(property.getAggregation());
        if (aggregation != null && !aggregation.isEmpty()) {
            json.addProperty("aggregation", aggregation);
        }

        appendBooleanProperty(json, "composite", safeBoolean(property.isComposite()));

        Object represents = invokeZeroArg(property, "getRepresents");
        if (represents instanceof Element) {
            json.add("represents", toJsonReference((Element) represents));
        }

        Stereotype flowPropertyStereo = getFlowPropertyStereotype(property);
        if (flowPropertyStereo != null) {
            String direction = readFlowPropertyDirection(property, flowPropertyStereo);
            if (direction != null && !direction.isEmpty()) {
                json.addProperty("direction", direction);
            }
        }
    }

    private static void appendPortLikeFields(JsonObject json, Element element) {
        appendBooleanProperty(json, "isConjugated", firstBoolean(
                invokeBooleanZeroArg(element, "isConjugated"),
                invokeBooleanZeroArg(element, "isIsConjugated")));
        appendBooleanProperty(json, "isService", invokeBooleanZeroArg(element, "isService"));
        appendBooleanProperty(json, "isBehavior", invokeBooleanZeroArg(element, "isBehavior"));
    }

    private static void appendParameterLikeFields(JsonObject json, Element element) {
        if (element instanceof Parameter) {
            String direction = stringifyEnumLike(((Parameter) element).getDirection());
            if (direction != null && !direction.isEmpty()) {
                json.addProperty("direction", direction);
            }
        }

        if (element instanceof ActivityParameterNode) {
            Parameter parameter = ((ActivityParameterNode) element).getParameter();
            if (parameter != null) {
                json.add("parameter", toJsonReference(parameter));
            }
        }
    }

    private static void appendStereotypeNames(JsonObject json, Element element) {
        try {
            List<Stereotype> stereotypes = StereotypesHelper.getStereotypes(element);
            if (stereotypes != null && !stereotypes.isEmpty()) {
                JsonArray stArray = new JsonArray();
                for (Stereotype st : stereotypes) {
                    if (st != null && st.getName() != null && !st.getName().isEmpty()) {
                        stArray.add(st.getName());
                    }
                }
                if (stArray.size() > 0) {
                    json.add("stereotypes", stArray);
                }
            }
        } catch (Exception e) {
            LOG.log(Level.FINE, "Could not read stereotypes for " + safeId(element), e);
        }
    }

    private static JsonElement serializeTaggedValue(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Boolean) {
            return new JsonPrimitive((Boolean) value);
        }
        if (value instanceof Number) {
            return new JsonPrimitive((Number) value);
        }
        if (value instanceof String) {
            return new JsonPrimitive((String) value);
        }
        if (value instanceof Character) {
            return new JsonPrimitive((Character) value);
        }
        if (value instanceof Element) {
            return toJsonCompact((Element) value);
        }
        if (value instanceof Collection<?>) {
            JsonArray array = new JsonArray();
            for (Object item : (Collection<?>) value) {
                JsonElement serialized = serializeTaggedValue(item);
                if (serialized != null) {
                    array.add(serialized);
                }
            }
            return array;
        }
        return new JsonPrimitive(String.valueOf(value));
    }

    private static Object invokeZeroArg(Object target, String methodName) {
        if (target == null) {
            return null;
        }
        try {
            Method method = target.getClass().getMethod(methodName);
            return method.invoke(target);
        } catch (Exception e) {
            return null;
        }
    }

    private static Integer invokeIntegerZeroArg(Object target, String methodName) {
        Object value = invokeZeroArg(target, methodName);
        if (value instanceof Number) {
            return ((Number) value).intValue();
        }
        return null;
    }

    private static Boolean invokeBooleanZeroArg(Object target, String methodName) {
        Object value = invokeZeroArg(target, methodName);
        if (value instanceof Boolean) {
            return (Boolean) value;
        }
        return null;
    }

    private static void appendIntegerProperty(JsonObject json, String key, Integer value) {
        if (value != null) {
            json.addProperty(key, value);
        }
    }

    private static void appendBooleanProperty(JsonObject json, String key, Boolean value) {
        if (value != null) {
            json.addProperty(key, value);
        }
    }

    private static Boolean firstBoolean(Boolean first, Boolean second) {
        return first != null ? first : second;
    }

    private static Boolean safeBoolean(boolean value) {
        return value;
    }

    private static String stringifyEnumLike(Object value) {
        if (value == null) {
            return null;
        }
        if (value instanceof Enum<?>) {
            return ((Enum<?>) value).name();
        }
        try {
            Method getName = value.getClass().getMethod("getName");
            Object name = getName.invoke(value);
            if (name != null) {
                String text = String.valueOf(name).trim();
                if (!text.isEmpty()) {
                    return text;
                }
            }
        } catch (Exception ignored) {
            // Fall back to String.valueOf below.
        }
        String text = String.valueOf(value).trim();
        return text.isEmpty() ? null : text;
    }

    private static int safeSize(Collection<?> collection) {
        return collection != null ? collection.size() : 0;
    }

    private static String safeId(Element element) {
        return element != null ? element.getID() : "<null>";
    }
}
