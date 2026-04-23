package com.claude.cameo.bridge.util;

import org.junit.Test;

import java.util.List;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertTrue;

public class CompartmentAliasResolverTest {

    @Test
    public void showPrefixedAliasesResolveToCompartmentCandidates() {
        assertEquals(
                List.of("Suppress Attributes"),
                CompartmentAliasResolver.candidatePropertyNames("showAttributes"));
        assertEquals(
                List.of("Suppress Parts", "Show Parts"),
                CompartmentAliasResolver.candidatePropertyNames("showParts"));
        assertEquals(
                List.of("Suppress Flow Properties", "Show Flow Properties"),
                CompartmentAliasResolver.candidatePropertyNames("showFlowProperties"));
        assertEquals(
                List.of("Show Tagged Values"),
                CompartmentAliasResolver.candidatePropertyNames("showTaggedValues"));
    }

    @Test
    public void suppressPrefixedAliasesReuseTheSameCompartmentCandidates() {
        assertEquals(
                List.of("Suppress Parts", "Show Parts"),
                CompartmentAliasResolver.candidatePropertyNames("suppressParts"));
        assertEquals(
                List.of("Suppress Proxy Ports", "Show Proxy Ports"),
                CompartmentAliasResolver.candidatePropertyNames("suppressProxyPorts"));
    }

    @Test
    public void unknownCompartmentAliasReturnsNoCandidates() {
        assertTrue(CompartmentAliasResolver.candidatePropertyNames("showNotARealCompartment").isEmpty());
    }
}
