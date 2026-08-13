#!/usr/bin/env python3
"""sync_skill_entries.py 的破坏性边界回归测试（仅使用临时 Git 仓库）。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

import sync_skill_entries as sync


class SkillSyncTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repo = self.base / "repo"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True)
        (self.repo / ".gitignore").write_text("skills/*/cache.bin\n", encoding="utf-8")
        self._add_skill("alpha", tracked=True)
        shared = self.repo / "skills" / "_shared" / "shared.py"
        shared.parent.mkdir(parents=True)
        shared.write_text("SHARED = True\n", encoding="utf-8")
        subprocess.run(
            ["git", "add", ".gitignore", "skills/alpha/SKILL.md", "skills/_shared/shared.py"],
            cwd=self.repo,
            check=True,
        )
        self.globals = (
            sync.REPO,
            sync.SOURCE_ROOT,
            sync.CODEX_ROOT,
            sync.CLAUDE_ROOT,
        )
        sync.REPO = self.repo
        sync.SOURCE_ROOT = self.repo / "skills"
        sync.CODEX_ROOT = self.repo / ".agents" / "skills"
        sync.CLAUDE_ROOT = self.repo / ".claude" / "skills"

    def tearDown(self) -> None:
        sync.REPO, sync.SOURCE_ROOT, sync.CODEX_ROOT, sync.CLAUDE_ROOT = self.globals
        self.temp.cleanup()

    def _add_skill(self, name: str, tracked: bool = False) -> Path:
        root = self.repo / "skills" / name
        root.mkdir(parents=True)
        (root / "SKILL.md").write_text(
            f"---\nname: {name}\ndescription: test\n---\n",
            encoding="utf-8",
        )
        if tracked:
            # setUp 尚未建立完整树时由调用方统一 git add。
            pass
        return root

    def test_sync_preserves_extra_entries_and_filters_ignored_cache(self) -> None:
        (self.repo / "skills" / "alpha" / "new.py").write_text("NEW = True\n", encoding="utf-8")
        (self.repo / "skills" / "alpha" / "cache.bin").write_text("ignored\n", encoding="utf-8")
        sync.CODEX_ROOT.mkdir(parents=True)
        external = self.repo / "external"
        external.mkdir()
        (sync.CODEX_ROOT / "custom").symlink_to(external, target_is_directory=True)
        sync.CLAUDE_ROOT.mkdir(parents=True)
        (sync.CLAUDE_ROOT / "custom-local").mkdir()
        (sync.CLAUDE_ROOT / "custom-local" / "keep").write_text("keep\n", encoding="utf-8")

        sync.sync_codex()
        sync.sync_claude()
        sync.sync_codex()
        sync.sync_claude()

        self.assertTrue((sync.CODEX_ROOT / "custom").is_symlink())
        self.assertTrue((sync.CLAUDE_ROOT / "custom-local" / "keep").is_file())
        self.assertTrue((sync.CLAUDE_ROOT / "alpha" / "new.py").is_file())
        self.assertFalse((sync.CLAUDE_ROOT / "alpha" / "cache.bin").exists())
        self.assertTrue((sync.CLAUDE_ROOT / "_shared" / "shared.py").is_file())

    def test_source_symlink_and_parent_symlink_are_rejected(self) -> None:
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "SKILL.md").write_text("---\nname: evil\ndescription: evil\n---\n")
        (self.repo / "skills" / "evil").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(sync.SyncError):
            sync.skill_names()

        (self.repo / "skills" / "evil").unlink()
        (self.repo / ".claude").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(sync.SyncError):
            sync._safe_generated_root(sync.CLAUDE_ROOT)

    def test_ignored_skill_is_not_split_brain(self) -> None:
        with (self.repo / ".gitignore").open("a", encoding="utf-8") as handle:
            handle.write("skills/private/\n")
        self._add_skill("private")
        self.assertEqual(sync.skill_names(), ["alpha"])
        sync.sync_codex()
        sync.sync_claude()
        self.assertFalse((sync.CODEX_ROOT / "private").exists())
        self.assertFalse((sync.CLAUDE_ROOT / "private").exists())
        self.assertEqual(sync.check_codex() + sync.check_claude(), [])

    def test_marker_path_injection_is_rejected(self) -> None:
        victim = self.base / "victim"
        victim.mkdir()
        sync.CLAUDE_ROOT.mkdir(parents=True)
        marker = sync.CLAUDE_ROOT / sync.CLAUDE_MARKER
        marker.write_text(json.dumps({"managed_top_level": [str(victim)]}), encoding="utf-8")
        with self.assertRaises(sync.SyncError):
            sync._claude_install_preflight(set())
        self.assertTrue(victim.is_dir())

    def test_install_failure_rolls_back_complete_previous_copy(self) -> None:
        sync.sync_claude()
        old_skill = sync.CLAUDE_ROOT / "alpha" / "SKILL.md"
        old_content = old_skill.read_text(encoding="utf-8")
        self._add_skill("beta")  # 未忽略的 untracked skill 也属于 Git-visible manifest。

        real_replace = os.replace
        installs = 0

        def fail_second_install(source: os.PathLike[str] | str, destination: os.PathLike[str] | str) -> None:
            nonlocal installs
            source_path = Path(source)
            destination_path = Path(destination)
            if ".skills-stage-" in str(source_path) and destination_path.parent == sync.CLAUDE_ROOT:
                installs += 1
                if installs == 2:
                    raise OSError("injected install failure")
            real_replace(source, destination)

        with mock.patch.object(sync.os, "replace", side_effect=fail_second_install):
            with self.assertRaises(sync.SyncError):
                sync.sync_claude()

        self.assertEqual(old_skill.read_text(encoding="utf-8"), old_content)
        self.assertFalse((sync.CLAUDE_ROOT / "beta").exists())
        marker = json.loads((sync.CLAUDE_ROOT / sync.CLAUDE_MARKER).read_text(encoding="utf-8"))
        self.assertEqual(set(marker["managed_top_level"]), {"alpha", "_shared"})


if __name__ == "__main__":
    unittest.main()
