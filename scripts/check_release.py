"""Check public source hygiene, knowledge pack hashes, and local Markdown links without network calls."""
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
EXCLUDE = {".git", "__pycache__", "build", "dist", ".venv", ".github-audit"}


def main():
    errors = []
    required = [
        "LICENSE", "README.md", "SECURITY.md", "THIRD_PARTY_NOTICES.md",
        "docs/AGENT-RECIPE.md", "wiki/index.md", "references/sources.md",
        "knowledge/gohighlevel/pack.json", "knowledge/gohighlevel/vault/index.md",
        "skills/cto-legends/SKILL.md", "assets/banner.webp", "assets/social-preview.png",
        "docs/catalog-entry.candidate.json", "docs/RELEASE-READINESS.md",
    ]
    for rel in required:
        if not (ROOT / rel).is_file():
            errors.append("Missing " + rel)
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if any(p in EXCLUDE or p.endswith(".egg-info") for p in relative.parts):
            continue
        if path.is_symlink():
            errors.append("Symlink: " + relative.as_posix())
        if not path.is_file():
            continue
        if path.name == ".env" or path.suffix.lower() in {".pem", ".key", ".ttf", ".otf"}:
            errors.append("Forbidden public file: " + relative.as_posix())
        if path.suffix in {".md", ".py", ".json", ".toml", ".yml"} and relative.as_posix() != "scripts/check_release.py":
            text = path.read_text(encoding="utf-8")
            if re.search(r"(?i)(?:[ce]:[\\/](?:users|empire|legends-)|ctolegends\.com)", text):
                errors.append("Private host reference: " + relative.as_posix())
            if "\u2014" in text or "\u2013" in text:
                errors.append("Forbidden em/en dash in: " + relative.as_posix())
            if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd]", text):
                errors.append("Forbidden control or replacement char in: " + relative.as_posix())
            if path.suffix == ".md":
                for link in re.findall(r"\]\(([^)\s]+)\)", text):
                    if "://" in link or link.startswith(("#", "mailto:")):
                        continue
                    target = link.split("#", 1)[0]
                    if target and not (path.parent / target).exists():
                        errors.append(f"Broken link in {relative}: {link}")
    router = ROOT / "skills/cto-legends/SKILL.md"
    if router.exists():
        expected = json.loads((ROOT / "docs/router-provenance.json").read_text(encoding="utf-8"))["sha256"]
        if hashlib.sha256(router.read_bytes()).hexdigest() != expected:
            errors.append("Router differs from its recorded canonical source.")
    pack_path = ROOT / "knowledge/gohighlevel/pack.json"
    if pack_path.exists():
        pack = json.loads(pack_path.read_text(encoding="utf-8"))
        if pack.get("schema") != "legends.knowledge-pack/v1" or pack.get("module") != "legends-gohighlevel":
            errors.append("Knowledge pack schema or module invalid.")
        vault_dir = ROOT / "knowledge/gohighlevel/vault"
        for item in pack.get("files", []):
            target = vault_dir / item["path"]
            if not target.is_file():
                errors.append(f"Missing knowledge pack file: {item['path']}")
            elif hashlib.sha256(target.read_bytes()).hexdigest() != item["sha256"]:
                errors.append(f"Knowledge pack hash mismatch: {item['path']}")
    print(json.dumps({"ok": not errors, "errors": errors}, indent=2))
    return bool(errors)


if __name__ == "__main__":
    sys.exit(main())
