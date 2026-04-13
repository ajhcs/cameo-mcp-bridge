import unittest
from unittest.mock import AsyncMock

from cameo_mcp import state_machine_semantics


class StateMachineSemanticsTests(unittest.IsolatedAsyncioTestCase):
    async def test_get_transition_triggers_parses_macro_json(self) -> None:
        bridge = AsyncMacroBridge(
            {
                "success": True,
                "result": (
                    '{"transitionId":"tr-1","triggerCount":1,"triggers":['
                    '{"id":"tg-1","eventType":"ChangeEvent","changeExpression":"when ready"}'
                    "]}"
                ),
            }
        )

        result = await state_machine_semantics.get_transition_triggers(
            "tr-1",
            bridge=bridge,
        )

        self.assertEqual("tr-1", result["transitionId"])
        self.assertEqual(1, result["triggerCount"])
        self.assertEqual("ChangeEvent", result["triggers"][0]["eventType"])
        bridge.execute_macro.assert_awaited_once()

    async def test_set_transition_trigger_builds_change_event_script(self) -> None:
        bridge = AsyncMacroBridge(
            {
                "success": True,
                "result": '{"transitionId":"tr-1","triggerCount":1,"triggers":[]}',
            }
        )

        await state_machine_semantics.set_transition_trigger(
            "tr-1",
            trigger_kind="change",
            expression="when ticket is inserted",
            name="TicketInserted",
            bridge=bridge,
        )

        script = bridge.execute_macro.await_args.args[0]
        self.assertIn("createChangeEventInstance", script)
        self.assertIn("GsonBuilder", script)
        self.assertNotIn("JsonOutput", script)
        self.assertIn('"when ticket is inserted"', script)
        self.assertIn('"TicketInserted"', script)

    async def test_set_transition_trigger_builds_signal_event_script(self) -> None:
        bridge = AsyncMacroBridge(
            {
                "success": True,
                "result": '{"transitionId":"tr-1","triggerCount":1,"triggers":[]}',
            }
        )

        await state_machine_semantics.set_transition_trigger(
            "tr-1",
            trigger_kind="signal",
            signal_id="sig-9",
            bridge=bridge,
        )

        script = bridge.execute_macro.await_args.args[0]
        self.assertIn("createSignalEventInstance", script)
        self.assertIn("GsonBuilder", script)
        self.assertNotIn("JsonOutput", script)
        self.assertIn('"sig-9"', script)

    async def test_set_transition_trigger_validates_required_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "change triggers require a non-empty expression"):
            await state_machine_semantics.set_transition_trigger(
                "tr-1",
                trigger_kind="change",
                expression="",
                bridge=AsyncMacroBridge({"success": True, "result": "{}"}),
            )

        with self.assertRaisesRegex(ValueError, "signal triggers require signal_id"):
            await state_machine_semantics.set_transition_trigger(
                "tr-1",
                trigger_kind="signal",
                bridge=AsyncMacroBridge({"success": True, "result": "{}"}),
            )

    async def test_get_state_behaviors_parses_macro_json(self) -> None:
        bridge = AsyncMacroBridge(
            {
                "success": True,
                "result": (
                    '{"stateId":"st-1","entry":{"body":"boot","language":"StructuredText"},'
                    '"doActivity":{"body":"wait","language":"StructuredText"},'
                    '"exit":{"body":"clear","language":"StructuredText"}}'
                ),
            }
        )

        result = await state_machine_semantics.get_state_behaviors(
            "st-1",
            bridge=bridge,
        )

        self.assertEqual("boot", result["entry"]["body"])
        self.assertEqual("wait", result["doActivity"]["body"])
        self.assertEqual("clear", result["exit"]["body"])

    async def test_set_state_behaviors_builds_opaque_behavior_script(self) -> None:
        bridge = AsyncMacroBridge(
            {
                "success": True,
                "result": '{"stateId":"st-1","entry":null,"doActivity":null,"exit":null}',
            }
        )

        await state_machine_semantics.set_state_behaviors(
            "st-1",
            entry="initialize reader",
            do_activity="wait for card",
            exit_behavior="clear display",
            language="StructuredText",
            clear_unspecified=True,
            bridge=bridge,
        )

        script = bridge.execute_macro.await_args.args[0]
        self.assertIn("createOpaqueBehaviorInstance", script)
        self.assertIn("GsonBuilder", script)
        self.assertNotIn("JsonOutput", script)
        self.assertIn('"initialize reader"', script)
        self.assertIn('"wait for card"', script)
        self.assertIn('"clear display"', script)
        self.assertIn('"StructuredText"', script)
        self.assertIn("clearUnspecified = true", script)

    async def test_execute_macro_json_raises_on_macro_failure(self) -> None:
        bridge = AsyncMacroBridge(
            {
                "success": False,
                "error": "boom",
                "output": "stack",
            }
        )

        with self.assertRaisesRegex(RuntimeError, "boom; output=stack"):
            await state_machine_semantics.get_state_behaviors("st-1", bridge=bridge)


class AsyncMacroBridge:
    def __init__(self, response):
        self.execute_macro = AsyncMock(return_value=response)


if __name__ == "__main__":
    unittest.main()
