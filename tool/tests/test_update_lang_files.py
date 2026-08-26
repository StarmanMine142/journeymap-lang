import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tool.update_lang_files import (
    build_commands,
    generate_legacy_lang_files,
    json_to_lang,
    legacy_lang_filename,
    run_update,
)


class BuildCommandsTest(unittest.TestCase):
    def test_build_commands_uses_expected_forge_toolkit_sequence(self):
        repo_root = Path("G:/MinecraftProjects/journeymap-lang")
        commands = build_commands(repo_root)

        self.assertEqual(3, len(commands))
        self.assertEqual(
            [
                "java",
                "-jar",
                str(repo_root / "tool" / "ForgeToolkit-1.1-all.jar"),
                "update",
                "src/main/resources/assets/journeymap/lang/en_us.json",
                "src/main/resources/assets/journeymap/lang/*.json",
            ],
            commands[0],
        )
        self.assertEqual("flatten", commands[1][3])
        self.assertEqual("sort", commands[2][3])

    @patch("tool.update_lang_files.subprocess.run")
    def test_run_update_executes_all_commands_in_repo_root(self, run_mock):
        repo_root = Path("G:/MinecraftProjects/journeymap-lang")

        run_update(repo_root)

        self.assertEqual(3, run_mock.call_count)
        first_call = run_mock.call_args_list[0]
        self.assertEqual(repo_root, first_call.kwargs["cwd"])
        self.assertTrue(first_call.kwargs["check"])


class LegacyLangFilenameTest(unittest.TestCase):
    def test_lowercase_style_keeps_locale_as_is(self):
        self.assertEqual("en_us.lang", legacy_lang_filename("en_us", "lowercase"))
        self.assertEqual("pt_br.lang", legacy_lang_filename("pt_br", "lowercase"))

    def test_region_upper_style_uppercases_region_subtag(self):
        self.assertEqual("en_US.lang", legacy_lang_filename("en_us", "region_upper"))
        self.assertEqual("pt_BR.lang", legacy_lang_filename("pt_br", "region_upper"))

    def test_region_upper_style_passes_through_language_only_locale(self):
        self.assertEqual("eo.lang", legacy_lang_filename("eo", "region_upper"))


class JsonToLangTest(unittest.TestCase):
    def test_comment_key_becomes_hash_line(self):
        self.assertEqual("# hello\n", json_to_lang({"_comment": "hello"}))

    def test_regular_entry_becomes_key_value_line(self):
        self.assertEqual("jm.key=Value\n", json_to_lang({"jm.key": "Value"}))

    def test_embedded_newline_is_escaped_to_literal_backslash_n(self):
        result = json_to_lang({"jm.key": "line one\nline two"})
        self.assertEqual("jm.key=line one\\nline two\n", result)

    def test_crlf_is_normalised_then_escaped(self):
        result = json_to_lang({"jm.key": "line one\r\nline two"})
        self.assertEqual("jm.key=line one\\nline two\n", result)

    def test_key_order_is_preserved(self):
        mapping = {"_comment": "c", "b.key": "B", "a.key": "A"}
        self.assertEqual("# c\nb.key=B\na.key=A\n", json_to_lang(mapping))


class GenerateLegacyLangFilesTest(unittest.TestCase):
    def _write_source(self, repo_root: Path, locale: str, mapping_json: str) -> None:
        source_dir = repo_root / "src/main/resources/assets/journeymap/lang"
        source_dir.mkdir(parents=True, exist_ok=True)
        (source_dir / f"{locale}.json").write_text(mapping_json, encoding="utf-8")

    def test_writes_lang_files_with_per_target_filename_case(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            repo_root = workspace / "journeymap-lang"
            self._write_source(repo_root, "en_us", '{"_comment": "c", "jm.key": "Value"}')
            # Targets must already be checked out (their common/ tree present) to receive files.
            for target in ("journeymap-1.12.2_6.0.0", "journeymap-1.7.10_6.0.0"):
                (workspace / target / "common").mkdir(parents=True, exist_ok=True)

            generate_legacy_lang_files(repo_root)

            lang_subpath = "common/src/main/resources/assets/journeymap/lang"
            lowercase = workspace / "journeymap-1.12.2_6.0.0" / lang_subpath / "en_us.lang"
            region_upper = workspace / "journeymap-1.7.10_6.0.0" / lang_subpath / "en_US.lang"

            self.assertTrue(lowercase.is_file())
            self.assertTrue(region_upper.is_file())
            # Both bytes-identical; only the file name case differs between eras.
            self.assertEqual(b"# c\njm.key=Value\n", lowercase.read_bytes())
            self.assertEqual(b"# c\njm.key=Value\n", region_upper.read_bytes())

    def test_writes_lf_line_endings_not_crlf(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            repo_root = workspace / "journeymap-lang"
            self._write_source(repo_root, "en_us", '{"a": "A", "b": "B"}')
            (workspace / "journeymap-1.12.2_6.0.0" / "common").mkdir(parents=True, exist_ok=True)
            (workspace / "journeymap-1.7.10_6.0.0" / "common").mkdir(parents=True, exist_ok=True)

            generate_legacy_lang_files(repo_root)

            out = (
                workspace
                / "journeymap-1.12.2_6.0.0"
                / "common/src/main/resources/assets/journeymap/lang/en_us.lang"
            )
            self.assertNotIn(b"\r\n", out.read_bytes())

    def test_missing_target_repo_is_skipped_without_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            repo_root = workspace / "journeymap-lang"
            self._write_source(repo_root, "en_us", '{"jm.key": "Value"}')
            # Only one target checked out; the other is absent and must be skipped silently.
            (workspace / "journeymap-1.12.2_6.0.0" / "common").mkdir(parents=True, exist_ok=True)

            generate_legacy_lang_files(repo_root)

            present = (
                workspace
                / "journeymap-1.12.2_6.0.0"
                / "common/src/main/resources/assets/journeymap/lang/en_us.lang"
            )
            absent = workspace / "journeymap-1.7.10_6.0.0"
            self.assertTrue(present.is_file())
            self.assertFalse(absent.exists())

    def test_no_lang_files_written_into_journeymap_lang_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            repo_root = workspace / "journeymap-lang"
            self._write_source(repo_root, "en_us", '{"jm.key": "Value"}')
            (workspace / "journeymap-1.12.2_6.0.0" / "common").mkdir(parents=True, exist_ok=True)
            (workspace / "journeymap-1.7.10_6.0.0" / "common").mkdir(parents=True, exist_ok=True)

            generate_legacy_lang_files(repo_root)

            stray = list(repo_root.rglob("*.lang"))
            self.assertEqual([], stray)


if __name__ == "__main__":
    unittest.main()
