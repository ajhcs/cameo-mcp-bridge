import unittest

from cameo_mcp.server import _mcp_result


class McpResultTests(unittest.TestCase):
    def test_mcp_result_returns_dict_by_default(self) -> None:
        payload = {"status": "ok", "port": 18740}

        result = _mcp_result(payload)

        self.assertIs(result, payload)


if __name__ == "__main__":
    unittest.main()
