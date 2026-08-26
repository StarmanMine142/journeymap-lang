import json
import subprocess
from pathlib import Path


LANG_SUBPATH = "src/main/resources/assets/journeymap/lang"
LANG_GLOB = f"{LANG_SUBPATH}/*.json"
EN_US_PATH = f"{LANG_SUBPATH}/en_us.json"

# Where each legacy (pre-JSON) JourneyMap version keeps its .lang files, and how the locale code maps to
# that version's file name. Minecraft loads a differently-named lang file per era:
#   1.12.2 (MC 1.11+): lowercase, e.g. en_us.lang  -> the locale code as-is
#   1.7.10           : mixed case,  e.g. en_US.lang -> language lowercase, region UPPERCASE
# The .lang files are GENERATED into these sibling repos from journeymap-lang's JSON source; they are
# deliberately NOT stored in journeymap-lang itself (see .gitignore). Paths are resolved relative to the
# journeymap-lang repo root's parent (the shared MinecraftProjects workspace); a target that is not checked
# out is skipped with a warning rather than failing the whole sync.
LEGACY_LANG_SUBPATH = "common/src/main/resources/assets/journeymap/lang"
LEGACY_TARGETS = [
    ("journeymap-1.12.2_6.0.0", "lowercase"),
    ("journeymap-1.7.10_6.0.0", "region_upper"),
]


def build_commands(repo_root: Path) -> list[list[str]]:
    jar_path = repo_root / "tool" / "ForgeToolkit-1.1-all.jar"
    jar_arg = str(jar_path)
    return [
        ["java", "-jar", jar_arg, "update", EN_US_PATH, LANG_GLOB],
        ["java", "-jar", jar_arg, "flatten", LANG_GLOB],
        ["java", "-jar", jar_arg, "sort", LANG_GLOB],
    ]


def run_update(repo_root: Path) -> None:
    for command in build_commands(repo_root):
        subprocess.run(command, cwd=repo_root, check=True)


def legacy_lang_filename(locale: str, style: str) -> str:
    """Map a lowercase JSON locale (e.g. ``en_us``) to a legacy ``.lang`` file name.

    ``lowercase`` keeps it as-is (1.12.2: ``en_us.lang``); ``region_upper`` uppercases the region subtag
    (1.7.10: ``en_US.lang``). Locales without a ``language_region`` shape are passed through unchanged.
    """
    if style == "region_upper":
        parts = locale.split("_")
        if len(parts) == 2:
            locale = f"{parts[0].lower()}_{parts[1].upper()}"
    return f"{locale}.lang"


def json_to_lang(mapping: dict) -> str:
    """Convert a flat JourneyMap locale JSON mapping to Minecraft ``.lang`` (key=value) text.

    Keys beginning with ``_`` (e.g. ``_comment``) become ``# comment`` lines; every other entry becomes a
    ``key=value`` line. Real newlines inside a value are escaped back to the literal two-character ``\\n``
    so each entry stays on a single line (Minecraft's .lang parser is line-based). Output uses ``\\n`` line
    endings and a trailing newline, matching the committed legacy files byte-for-byte.
    """
    lines = []
    for key, value in mapping.items():
        text = value.replace("\r\n", "\n").replace("\n", "\\n")
        if key.startswith("_"):
            lines.append(f"# {text}")
        else:
            lines.append(f"{key}={text}")
    return "\n".join(lines) + "\n"


def generate_legacy_lang_files(repo_root: Path) -> None:
    """Regenerate the .lang files for every legacy target from journeymap-lang's normalized JSON source."""
    source_dir = repo_root / LANG_SUBPATH
    json_files = sorted(source_dir.glob("*.json"))
    workspace = repo_root.parent

    for repo_name, style in LEGACY_TARGETS:
        repo_dir = workspace / repo_name
        if not repo_dir.is_dir():
            print(f"skip {repo_name}: repo not found at {repo_dir}")
            continue
        lang_dir = repo_dir / LEGACY_LANG_SUBPATH
        lang_dir.mkdir(parents=True, exist_ok=True)
        for json_file in json_files:
            mapping = json.loads(json_file.read_text(encoding="utf-8"))
            lang_text = json_to_lang(mapping)
            out_file = lang_dir / legacy_lang_filename(json_file.stem, style)
            # Write bytes with explicit LF so Windows does not translate to CRLF.
            out_file.write_bytes(lang_text.encode("utf-8"))
        print(f"generated {len(json_files)} .lang files -> {lang_dir}")


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    run_update(repo_root)
    generate_legacy_lang_files(repo_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
