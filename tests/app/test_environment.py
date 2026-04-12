from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from eve_craft.app.environment import load_dotenv_file


class DotenvLoaderTests(unittest.TestCase):
    def test_load_dotenv_file_reads_simple_key_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dotenv_path = Path(temp_dir) / ".env"
            dotenv_path.write_text(
                "\n".join(
                    (
                        "# comment",
                        "EVE_CRAFT_ESI_CLIENT_ID=test-client",
                        "EVE_CRAFT_ESI_CLIENT_SECRET=\"test-secret\"",
                        "export EVE_CRAFT_ESI_CALLBACK_URL=http://127.0.0.1:8080/callback",
                    )
                ),
                encoding="utf-8",
            )

            previous_client_id = os.environ.pop("EVE_CRAFT_ESI_CLIENT_ID", None)
            previous_client_secret = os.environ.pop("EVE_CRAFT_ESI_CLIENT_SECRET", None)
            previous_callback = os.environ.pop("EVE_CRAFT_ESI_CALLBACK_URL", None)
            try:
                loaded = load_dotenv_file(dotenv_path)
                self.assertEqual("test-client", os.environ["EVE_CRAFT_ESI_CLIENT_ID"])
                self.assertEqual("test-secret", os.environ["EVE_CRAFT_ESI_CLIENT_SECRET"])
                self.assertEqual("http://127.0.0.1:8080/callback", os.environ["EVE_CRAFT_ESI_CALLBACK_URL"])
                self.assertEqual(3, len(loaded))
            finally:
                self._restore_env("EVE_CRAFT_ESI_CLIENT_ID", previous_client_id)
                self._restore_env("EVE_CRAFT_ESI_CLIENT_SECRET", previous_client_secret)
                self._restore_env("EVE_CRAFT_ESI_CALLBACK_URL", previous_callback)

    def test_load_dotenv_file_does_not_override_existing_values_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            dotenv_path = Path(temp_dir) / ".env"
            dotenv_path.write_text("EVE_CRAFT_ESI_CLIENT_ID=file-client", encoding="utf-8")

            previous_client_id = os.environ.get("EVE_CRAFT_ESI_CLIENT_ID")
            os.environ["EVE_CRAFT_ESI_CLIENT_ID"] = "existing-client"
            try:
                loaded = load_dotenv_file(dotenv_path, override=False)
                self.assertEqual("existing-client", os.environ["EVE_CRAFT_ESI_CLIENT_ID"])
                self.assertEqual({}, loaded)
            finally:
                self._restore_env("EVE_CRAFT_ESI_CLIENT_ID", previous_client_id)

    @staticmethod
    def _restore_env(key: str, value: str | None) -> None:
        if value is None:
            os.environ.pop(key, None)
            return

        os.environ[key] = value
