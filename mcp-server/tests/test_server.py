import unittest
from unittest.mock import AsyncMock, patch

from cameo_mcp.server import (
    _mcp_result,
    cameo_get_capabilities,
    cameo_list_methodology_packs,
)


class McpResultTests(unittest.TestCase):
    def test_mcp_result_returns_dict_by_default(self) -> None:
        payload = {"status": "ok", "port": 18740}

        result = _mcp_result(payload)

        self.assertIs(result, payload)


class ServerToolTests(unittest.IsolatedAsyncioTestCase):
    async def test_cameo_get_capabilities_returns_native_dict(self) -> None:
        payload = {"pluginVersion": "1.0.0", "compatibility": {"clientCompatible": True}}

        with patch(
            "cameo_mcp.server.client.get_capabilities",
            new=AsyncMock(return_value=payload),
        ) as get_capabilities:
            result = await cameo_get_capabilities()

        self.assertIs(result, payload)
        get_capabilities.assert_awaited_once_with()

    async def test_cameo_list_methodology_packs_returns_native_dict(self) -> None:
        payload = {"count": 1, "packs": [{"id": "oosem"}]}

        with patch(
            "cameo_mcp.server.list_methodology_packs",
            return_value=payload,
        ) as list_packs:
            result = await cameo_list_methodology_packs()

        self.assertIs(result, payload)
        list_packs.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
