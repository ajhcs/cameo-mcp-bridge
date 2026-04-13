"""Structured state-machine semantics helpers backed by the macro bridge.

This module adds a typed Python surface for state-machine behaviors that are
not yet covered by native Java REST endpoints. It intentionally uses the
existing macro bridge under the hood so MCP clients can work with explicit
parameters instead of hand-writing Groovy.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from cameo_mcp import client as default_bridge_client


def _json_literal(value: Any) -> str:
    return json.dumps(value)


def _groovy_bool(value: bool) -> str:
    return "true" if value else "false"


def _format_macro_error(result: dict[str, Any]) -> str:
    detail = str(result.get("error") or "macro execution failed")
    output = str(result.get("output") or "")
    if output:
        detail += f"; output={output}"
    return detail


async def _execute_macro_json(script: str, bridge: Any) -> dict[str, Any]:
    result = await bridge.execute_macro(script)
    if not result.get("success"):
        raise RuntimeError(_format_macro_error(result))

    payload = result.get("result")
    if not isinstance(payload, str):
        raise RuntimeError(
            "State-machine macro returned a non-string result payload: "
            f"{payload!r}"
        )

    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "State-machine macro returned invalid JSON: "
            f"{payload!r}"
        ) from exc

    if not isinstance(parsed, dict):
        raise RuntimeError(
            "State-machine macro returned a non-object JSON payload: "
            f"{parsed!r}"
        )
    return parsed


def _transition_trigger_payload_script(transition_id: str) -> str:
    return f"""
import com.google.gson.GsonBuilder

def gson = new GsonBuilder().disableHtmlEscaping().create()

def transition = project.getElementByID({_json_literal(transition_id)})
if (transition == null) {{
    throw new IllegalArgumentException("Transition not found: " + {_json_literal(transition_id)})
}}

def triggerPayload = {{ trigger ->
    def event = null
    def signal = null
    def changeExpression = null
    try {{
        event = trigger?.event
    }} catch (ignored) {{}}
    try {{
        signal = event?.signal
    }} catch (ignored) {{}}
    try {{
        changeExpression = event?.changeExpression
    }} catch (ignored) {{}}

    def expressionText = null
    if (changeExpression != null) {{
        try {{
            expressionText = changeExpression?.value
        }} catch (ignored) {{
            expressionText = String.valueOf(changeExpression)
        }}
    }}

    return [
        id: trigger?.ID,
        name: trigger?.metaClass?.hasProperty(trigger, "name") ? (trigger?.name ?: "") : "",
        eventId: event?.ID,
        eventType: event?.getClass()?.getSimpleName() ?: "",
        signalId: signal?.ID,
        signalName: signal?.metaClass?.hasProperty(signal, "name") ? signal?.name : null,
        changeExpression: expressionText,
    ]
}}

def triggers = []
for (trigger in (transition?.trigger ?: [])) {{
    triggers << triggerPayload(trigger)
}}

return gson.toJson([
    transitionId: transition.ID,
    triggerCount: triggers.size(),
    triggers: triggers,
])
""".strip()


def _set_transition_trigger_script(
    transition_id: str,
    *,
    trigger_kind: str,
    expression: Optional[str],
    signal_id: Optional[str],
    name: Optional[str],
    replace: bool,
) -> str:
    return f"""
import com.google.gson.GsonBuilder
import com.nomagic.magicdraw.openapi.uml.ModelElementsManager
import com.nomagic.magicdraw.openapi.uml.SessionManager

def gson = new GsonBuilder().disableHtmlEscaping().create()

def transition = project.getElementByID({_json_literal(transition_id)})
if (transition == null) {{
    throw new IllegalArgumentException("Transition not found: " + {_json_literal(transition_id)})
}}

def triggerKind = {_json_literal(trigger_kind)}
def triggerName = {_json_literal(name)}
def signalId = {_json_literal(signal_id)}
def expressionText = {_json_literal(expression)}
def replaceExisting = {_groovy_bool(replace)}

def resolveEventOwner = {{ element ->
    def cursor = element
    while (cursor != null) {{
        if (cursor?.getClass()?.getSimpleName() == "StateMachine") {{
            return cursor
        }}
        try {{
            cursor = cursor?.owner
        }} catch (ignored) {{
            cursor = null
        }}
    }}
    return project.getPrimaryModel()
}}

def serializeTriggers = {{
    def triggers = []
    for (trigger in (transition?.trigger ?: [])) {{
        def event = null
        def signal = null
        def changeExpression = null
        try {{
            event = trigger?.event
        }} catch (ignored) {{}}
        try {{
            signal = event?.signal
        }} catch (ignored) {{}}
        try {{
            changeExpression = event?.changeExpression
        }} catch (ignored) {{}}
        def expressionValue = null
        if (changeExpression != null) {{
            try {{
                expressionValue = changeExpression?.value
            }} catch (ignored) {{
                expressionValue = String.valueOf(changeExpression)
            }}
        }}
        triggers << [
            id: trigger?.ID,
            name: trigger?.metaClass?.hasProperty(trigger, "name") ? (trigger?.name ?: "") : "",
            eventId: event?.ID,
            eventType: event?.getClass()?.getSimpleName() ?: "",
            signalId: signal?.ID,
            signalName: signal?.metaClass?.hasProperty(signal, "name") ? signal?.name : null,
            changeExpression: expressionValue,
        ]
    }}
    return triggers
}}

SessionManager.getInstance().createSession(project, "MCP Set Transition Trigger")
try {{
    if (replaceExisting) {{
        def existing = new ArrayList(transition?.trigger ?: [])
        for (trigger in existing) {{
            try {{
                ModelElementsManager.getInstance().removeElement(trigger)
            }} catch (ignored) {{
                transition?.trigger?.remove(trigger)
            }}
        }}
    }}

    def trigger = ef.createTriggerInstance()
    if (triggerName != null && triggerName.trim()) {{
        trigger.name = triggerName
    }}

    def eventOwner = resolveEventOwner(transition)
    if (triggerKind == "change") {{
        if (expressionText == null || !expressionText.trim()) {{
            throw new IllegalArgumentException("Change triggers require a non-empty expression")
        }}
        def event = ef.createChangeEventInstance()
        def literal = ef.createLiteralStringInstance()
        literal.value = expressionText
        event.changeExpression = literal
        ModelElementsManager.getInstance().addElement(event, eventOwner)
        trigger.event = event
    }} else if (triggerKind == "signal") {{
        if (signalId == null || !signalId.trim()) {{
            throw new IllegalArgumentException("Signal triggers require signal_id")
        }}
        def signal = project.getElementByID(signalId)
        if (signal == null) {{
            throw new IllegalArgumentException("Signal not found: " + signalId)
        }}
        def event = ef.createSignalEventInstance()
        event.signal = signal
        ModelElementsManager.getInstance().addElement(event, eventOwner)
        trigger.event = event
    }} else {{
        throw new IllegalArgumentException("Unsupported trigger kind: " + triggerKind)
    }}

    ModelElementsManager.getInstance().addElement(trigger, transition)
    SessionManager.getInstance().closeSession(project)
}} catch (Exception e) {{
    SessionManager.getInstance().cancelSession(project)
    throw e
}}

def triggers = serializeTriggers()
return gson.toJson([
    transitionId: transition.ID,
    triggerCount: triggers.size(),
    triggers: triggers,
])
""".strip()


def _state_behaviors_payload_script(state_id: str) -> str:
    return f"""
import com.google.gson.GsonBuilder

def gson = new GsonBuilder().disableHtmlEscaping().create()

def state = project.getElementByID({_json_literal(state_id)})
if (state == null) {{
    throw new IllegalArgumentException("State not found: " + {_json_literal(state_id)})
}}

def behaviorPayload = {{ behavior ->
    if (behavior == null) {{
        return null
    }}
    def bodyText = null
    def languageName = null
    try {{
        if (behavior?.body && behavior.body.size() > 0) {{
            bodyText = behavior.body[0]
        }}
    }} catch (ignored) {{}}
    try {{
        if (behavior?.language && behavior.language.size() > 0) {{
            languageName = behavior.language[0]
        }}
    }} catch (ignored) {{}}
    return [
        id: behavior?.ID,
        name: behavior?.metaClass?.hasProperty(behavior, "name") ? (behavior?.name ?: "") : "",
        body: bodyText,
        language: languageName,
        humanType: behavior?.humanType ?: behavior?.getClass()?.getSimpleName(),
    ]
}}

return gson.toJson([
    stateId: state.ID,
    stateName: state?.metaClass?.hasProperty(state, "name") ? (state?.name ?: "") : "",
    entry: behaviorPayload(state?.entry),
    doActivity: behaviorPayload(state?.doActivity),
    exit: behaviorPayload(state?.exit),
])
""".strip()


def _set_state_behaviors_script(
    state_id: str,
    *,
    entry: Optional[str],
    do_activity: Optional[str],
    exit_behavior: Optional[str],
    language: str,
    clear_unspecified: bool,
) -> str:
    return f"""
import com.google.gson.GsonBuilder
import com.nomagic.magicdraw.openapi.uml.ModelElementsManager
import com.nomagic.magicdraw.openapi.uml.SessionManager

def gson = new GsonBuilder().disableHtmlEscaping().create()

def state = project.getElementByID({_json_literal(state_id)})
if (state == null) {{
    throw new IllegalArgumentException("State not found: " + {_json_literal(state_id)})
}}

def languageName = {_json_literal(language)}
def entryText = {_json_literal(entry)}
def doText = {_json_literal(do_activity)}
def exitText = {_json_literal(exit_behavior)}
def clearUnspecified = {_groovy_bool(clear_unspecified)}

def behaviorPayload = {{ behavior ->
    if (behavior == null) {{
        return null
    }}
    def bodyText = null
    def behaviorLanguage = null
    try {{
        if (behavior?.body && behavior.body.size() > 0) {{
            bodyText = behavior.body[0]
        }}
    }} catch (ignored) {{}}
    try {{
        if (behavior?.language && behavior.language.size() > 0) {{
            behaviorLanguage = behavior.language[0]
        }}
    }} catch (ignored) {{}}
    return [
        id: behavior?.ID,
        name: behavior?.metaClass?.hasProperty(behavior, "name") ? (behavior?.name ?: "") : "",
        body: bodyText,
        language: behaviorLanguage,
        humanType: behavior?.humanType ?: behavior?.getClass()?.getSimpleName(),
    ]
}}

def assignBehavior = {{ slotName, newBehavior ->
    switch (slotName) {{
        case "entry":
            state.entry = newBehavior
            break
        case "doActivity":
            state.doActivity = newBehavior
            break
        case "exit":
            state.exit = newBehavior
            break
        default:
            throw new IllegalArgumentException("Unsupported state behavior slot: " + slotName)
    }}
}}

def currentBehavior = {{ slotName ->
    switch (slotName) {{
        case "entry":
            return state.entry
        case "doActivity":
            return state.doActivity
        case "exit":
            return state.exit
        default:
            throw new IllegalArgumentException("Unsupported state behavior slot: " + slotName)
    }}
}}

def applyBehavior = {{ slotName, bodyText ->
    def existing = currentBehavior(slotName)
    if (bodyText == null) {{
        if (clearUnspecified) {{
            assignBehavior(slotName, null)
        }}
        return
    }}

    if (!bodyText.trim()) {{
        assignBehavior(slotName, null)
        return
    }}

    def behavior = existing
    if (behavior == null || behavior?.getClass()?.getSimpleName() != "OpaqueBehavior") {{
        behavior = ef.createOpaqueBehaviorInstance()
        behavior.name = ((state?.name ?: "State") + " " + slotName)
        ModelElementsManager.getInstance().addElement(behavior, state)
    }}

    try {{
        behavior.body.clear()
    }} catch (ignored) {{}}
    behavior.body.add(bodyText)

    try {{
        behavior.language.clear()
    }} catch (ignored) {{}}
    behavior.language.add(languageName)

    assignBehavior(slotName, behavior)
}}

SessionManager.getInstance().createSession(project, "MCP Set State Behaviors")
try {{
    applyBehavior("entry", entryText)
    applyBehavior("doActivity", doText)
    applyBehavior("exit", exitText)
    SessionManager.getInstance().closeSession(project)
}} catch (Exception e) {{
    SessionManager.getInstance().cancelSession(project)
    throw e
}}

return gson.toJson([
    stateId: state.ID,
    stateName: state?.metaClass?.hasProperty(state, "name") ? (state?.name ?: "") : "",
    entry: behaviorPayload(state?.entry),
    doActivity: behaviorPayload(state?.doActivity),
    exit: behaviorPayload(state?.exit),
])
""".strip()


async def get_transition_triggers(
    transition_id: str,
    *,
    bridge: Any = default_bridge_client,
) -> dict[str, Any]:
    """Read the structured trigger/event state for one transition."""
    script = _transition_trigger_payload_script(transition_id)
    return await _execute_macro_json(script, bridge)


async def set_transition_trigger(
    transition_id: str,
    *,
    trigger_kind: str,
    expression: Optional[str] = None,
    signal_id: Optional[str] = None,
    name: Optional[str] = None,
    replace: bool = True,
    bridge: Any = default_bridge_client,
) -> dict[str, Any]:
    """Create or replace one transition trigger with explicit semantics."""
    normalized_kind = trigger_kind.strip().lower()
    if normalized_kind not in {"change", "signal"}:
        raise ValueError("trigger_kind must be 'change' or 'signal'")
    if normalized_kind == "change" and (expression is None or not expression.strip()):
        raise ValueError("change triggers require a non-empty expression")
    if normalized_kind == "signal" and (signal_id is None or not signal_id.strip()):
        raise ValueError("signal triggers require signal_id")

    script = _set_transition_trigger_script(
        transition_id,
        trigger_kind=normalized_kind,
        expression=expression,
        signal_id=signal_id,
        name=name,
        replace=replace,
    )
    return await _execute_macro_json(script, bridge)


async def get_state_behaviors(
    state_id: str,
    *,
    bridge: Any = default_bridge_client,
) -> dict[str, Any]:
    """Read the structured entry/do/exit behavior payloads for one state."""
    script = _state_behaviors_payload_script(state_id)
    return await _execute_macro_json(script, bridge)


async def set_state_behaviors(
    state_id: str,
    *,
    entry: Optional[str] = None,
    do_activity: Optional[str] = None,
    exit_behavior: Optional[str] = None,
    language: str = "Opaque",
    clear_unspecified: bool = False,
    bridge: Any = default_bridge_client,
) -> dict[str, Any]:
    """Set structured entry/do/exit opaque behaviors for one state.

    Notes:
    - Passing an empty string for a specific slot clears that slot.
    - Omitting a slot leaves it unchanged unless `clear_unspecified=True`.
    """
    if language is None or not language.strip():
        raise ValueError("language must be a non-empty string")

    script = _set_state_behaviors_script(
        state_id,
        entry=entry,
        do_activity=do_activity,
        exit_behavior=exit_behavior,
        language=language,
        clear_unspecified=clear_unspecified,
    )
    return await _execute_macro_json(script, bridge)
