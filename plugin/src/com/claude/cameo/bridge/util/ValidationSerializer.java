package com.claude.cameo.bridge.util;

import com.google.gson.JsonArray;
import com.google.gson.JsonObject;
import com.nomagic.magicdraw.annotation.Annotation;
import com.nomagic.magicdraw.validation.RuleViolationResult;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Constraint;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Element;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.EnumerationLiteral;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.NamedElement;
import com.nomagic.uml2.ext.magicdraw.classes.mdkernel.Package;

import java.util.Collection;

public final class ValidationSerializer {

    private ValidationSerializer() {
    }

    public static JsonObject suite(Package suite) {
        JsonObject json = ElementSerializer.toJsonReference(suite);
        json.addProperty("suiteId", suite.getID());
        json.addProperty("suiteName", safeName(suite));
        json.addProperty("discoveryType", "package");
        return json;
    }

    public static JsonObject constraint(Constraint constraint) {
        JsonObject json = ElementSerializer.toJsonReference(constraint);
        json.addProperty("constraintId", constraint.getID());
        json.addProperty("constraintName", safeName(constraint));
        json.addProperty("discoveryType", "constraint");
        return json;
    }

    public static JsonObject finding(RuleViolationResult result) {
        JsonObject json = new JsonObject();
        json.addProperty("message", OptionalCapabilitySupport.safe(result.getErrorMessage()));
        json.addProperty("ignored", result.isIgnored());
        json.addProperty("systemValidationResult", result.isSystemValidationResult());

        Constraint rule = result.getRule();
        if (rule != null) {
            json.add("rule", constraint(rule));
        }

        Annotation annotation = result.getAnnotation();
        if (annotation != null) {
            JsonObject annotationJson = new JsonObject();
            annotationJson.addProperty("kind", OptionalCapabilitySupport.safe(annotation.getKind()));
            annotationJson.addProperty("text", OptionalCapabilitySupport.safe(annotation.getText()));
            annotationJson.addProperty("toolTipText", OptionalCapabilitySupport.safe(annotation.getToolTipText()));
            EnumerationLiteral severity = annotation.getSeverity();
            if (severity != null) {
                annotationJson.add("severity", ElementSerializer.toJsonReference(severity));
            }
            json.add("annotation", annotationJson);
        }

        Object targetObject = result.getTargetObject();
        if (targetObject instanceof Element) {
            json.add("target", ElementSerializer.toJsonReference((Element) targetObject));
        } else if (result.getElement() instanceof Element) {
            json.add("target", ElementSerializer.toJsonReference((Element) result.getElement()));
        } else if (targetObject != null) {
            JsonObject target = new JsonObject();
            target.addProperty("className", targetObject.getClass().getName());
            target.addProperty("string", String.valueOf(targetObject));
            json.add("target", target);
        }

        Object parentObject = result.getParentObject();
        if (parentObject instanceof Element) {
            json.add("parent", ElementSerializer.toJsonReference((Element) parentObject));
        }

        return json;
    }

    public static JsonArray findings(Collection<RuleViolationResult> results) {
        JsonArray array = new JsonArray();
        if (results == null) {
            return array;
        }
        for (RuleViolationResult result : results) {
            if (result != null) {
                array.add(finding(result));
            }
        }
        return array;
    }

    private static String safeName(NamedElement element) {
        String name = element.getName();
        return name == null ? "" : name;
    }
}
