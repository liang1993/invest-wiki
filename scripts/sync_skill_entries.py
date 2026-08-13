#!/usr/bin/env python3
"""同步仓库 skill 到各 harness 的发现目录。

源目录始终是 ``skills/``：

- Codex：在 ``.agents/skills/`` 建立受版本控制的目录符号链接。Codex 官方支持
  symlink，链接只负责发现，不复制数据。
- Claude Code：在 ``.claude/skills/`` 建立隔离副本。这里刻意不用符号链接，避免
  Claude Desktop/插件同步器清理发现目录时沿链接误删 ``skills/`` 真源。

Claude 副本只包含 Git 跟踪文件和未被 gitignore 的未跟踪文件，避免复制回测缓存。
``_shared`` 也会复制过去供 skill 脚本相对 import，但它没有 SKILL.md，不会被当作
独立 skill。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parent.parent
SOURCE_ROOT = REPO / "skills"
CODEX_ROOT = REPO / ".agents" / "skills"
CLAUDE_ROOT = REPO / ".claude" / "skills"
CLAUDE_MARKER = ".generated-by-invest-wiki-sync-skills"


class SyncError(RuntimeError):
    pass


def _git_visible_files() -> list[Path]:
    result = subprocess.run(
        [
            "git",
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            "skills",
        ],
        cwd=REPO,
        check=True,
        capture_output=True,
    )
    files = []
    for raw in result.stdout.split(b"\0"):
        if not raw:
            continue
        rel = Path(os.fsdecode(raw))
        source = REPO / rel
        if source.is_symlink():
            raise SyncError(f"skills/ 源内禁止符号链接：{source}")
        cursor = SOURCE_ROOT
        try:
            nested = rel.relative_to("skills")
        except ValueError as exc:
            raise SyncError(f"Git manifest 出现 skills/ 外路径：{rel}") from exc
        for part in nested.parts[:-1]:
            cursor /= part
            if cursor.is_symlink():
                raise SyncError(f"skills/ 源路径含符号链接目录：{cursor}")
        if source.is_file():
            files.append(rel)
    return sorted(files)


def _reject_top_level_source_symlinks() -> None:
    if not SOURCE_ROOT.is_dir() or SOURCE_ROOT.is_symlink():
        raise SyncError(f"skills/ 源目录缺失或为符号链接：{SOURCE_ROOT}")
    with os.scandir(SOURCE_ROOT) as entries:
        for entry in entries:
            if entry.is_symlink():
                raise SyncError(f"skills/ 顶层禁止符号链接：{entry.path}")


def skill_names(files: list[Path] | None = None) -> list[str]:
    """只从 Git-visible SKILL.md 推导 skill 集合，保证发现与复制同一 manifest。"""
    _reject_top_level_source_symlinks()
    visible = _git_visible_files() if files is None else files
    names = {
        rel.parts[1]
        for rel in visible
        if len(rel.parts) == 3
        and rel.parts[0] == "skills"
        and rel.parts[1] != "_shared"
        and rel.parts[2] == "SKILL.md"
    }
    return sorted(names)


def _safe_generated_root(root: Path) -> None:
    try:
        relative = root.relative_to(REPO)
    except ValueError as exc:
        raise SyncError(f"生成目录不在仓库内：{root}") from exc
    cursor = REPO
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise SyncError(f"拒绝操作含符号链接的生成目录路径：{cursor}")
    root.mkdir(parents=True, exist_ok=True)
    if root.resolve().parent != root.parent.resolve():
        raise SyncError(f"生成目录解析异常：{root}")


def _validate_top_level_names(names: set[str], source: str) -> None:
    for name in names:
        if not name or name in {".", ".."} or Path(name).name != name:
            raise SyncError(f"{source} 含非法顶层条目名：{name!r}")


def sync_codex() -> int:
    """在 .agents/skills 创建到真实源的相对链接。"""
    _safe_generated_root(CODEX_ROOT)
    names = skill_names()
    expected = set(names)
    for entry in CODEX_ROOT.iterdir():
        if entry.name in expected:
            continue
        # 只清理由本仓库旧 skill 留下的失效链接；额外的用户/组织 skill 原样保留。
        if entry.is_symlink() and entry.resolve(strict=False).is_relative_to(SOURCE_ROOT.resolve()):
            entry.unlink()

    for name in names:
        link = CODEX_ROOT / name
        target = Path("..") / ".." / "skills" / name
        if link.is_symlink() and Path(os.readlink(link)) == target:
            continue
        if link.exists() or link.is_symlink():
            if not link.is_symlink():
                raise SyncError(f"Codex skill 入口不是符号链接，拒绝覆盖：{link}")
            link.unlink()
        link.symlink_to(target, target_is_directory=True)
    return len(names)


def _read_claude_managed_entries() -> set[str]:
    marker = CLAUDE_ROOT / CLAUDE_MARKER
    if marker.is_symlink():
        raise SyncError(f"拒绝读取或覆盖符号链接 marker：{marker}")
    if not marker.is_file():
        # 旧架构迁移：只认定指向本仓库 skills/ 的顶层链接为可清理条目。
        return {
            entry.name
            for entry in CLAUDE_ROOT.iterdir()
            if entry.is_symlink()
            and entry.resolve(strict=False).is_relative_to(SOURCE_ROOT.resolve())
        }
    try:
        data = json.loads(marker.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # 兼容本脚本早期开发版 marker；只接管当前标准名称，不碰额外条目。
        return set(skill_names()) | {"_shared"}
    managed = data.get("managed_top_level")
    if not isinstance(managed, list) or any(not isinstance(name, str) for name in managed):
        raise SyncError(f"Claude skill marker 格式错误：{marker}")
    names = set(managed)
    _validate_top_level_names(names, str(marker))
    return names


def _claude_install_preflight(expected: set[str]) -> set[str]:
    """校验 Claude 安装目标，返回上一版由本脚本管理的顶层条目。"""
    _validate_top_level_names(expected, "预期 Claude skill 列表")
    managed = _read_claude_managed_entries()

    # 先检测新名称与用户内容的碰撞，再删除任何旧副本；报错时保持现场不变。
    collisions = [
        CLAUDE_ROOT / name
        for name in expected - managed
        if (CLAUDE_ROOT / name).exists() or (CLAUDE_ROOT / name).is_symlink()
    ]
    if collisions:
        rendered = ", ".join(str(path) for path in sorted(collisions))
        raise SyncError(f"Claude skill 目标与非生成内容冲突，拒绝覆盖：{rendered}")
    return managed


def _remove_entry(entry: Path) -> None:
    if not entry.exists() and not entry.is_symlink():
        return
    if entry.is_symlink() or entry.is_file():
        entry.unlink()
    elif entry.is_dir():
        shutil.rmtree(entry)
    else:
        raise SyncError(f"无法安全清理 Claude skill 条目：{entry}")


def _install_claude_stage(stage: Path, expected: set[str], marker_text: str) -> None:
    """同文件系统安装；任何移动/写 marker 失败时恢复上一版。"""
    _safe_generated_root(CLAUDE_ROOT)
    previous = _claude_install_preflight(expected)
    backup = stage / ".previous"
    backup.mkdir()
    marker = CLAUDE_ROOT / CLAUDE_MARKER
    backup_marker = backup / CLAUDE_MARKER
    moved_old: list[str] = []
    installed_new: list[str] = []

    try:
        if marker.exists():
            os.replace(marker, backup_marker)
        for name in sorted(previous):
            entry = CLAUDE_ROOT / name
            if entry.exists() or entry.is_symlink():
                os.replace(entry, backup / name)
                moved_old.append(name)

        for name in sorted(expected):
            staged_entry = stage / name
            if staged_entry.exists():
                os.replace(staged_entry, CLAUDE_ROOT / name)
                installed_new.append(name)

        staged_marker = stage / CLAUDE_MARKER
        staged_marker.write_text(marker_text, encoding="utf-8")
        os.replace(staged_marker, marker)
    except Exception as install_error:
        try:
            for name in installed_new:
                _remove_entry(CLAUDE_ROOT / name)
            if marker.exists() or marker.is_symlink():
                _remove_entry(marker)
            for name in moved_old:
                saved = backup / name
                if saved.exists() or saved.is_symlink():
                    os.replace(saved, CLAUDE_ROOT / name)
            if backup_marker.exists():
                os.replace(backup_marker, marker)
        except Exception as rollback_error:
            raise SyncError(
                f"Claude skill 安装失败且回滚失败：install={install_error}; rollback={rollback_error}"
            ) from rollback_error
        raise SyncError(f"Claude skill 安装失败，已恢复上一版：{install_error}") from install_error


def _copy_entry(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.is_symlink():
        raise SyncError(f"Claude 隔离副本拒绝复制符号链接，请改为真实文件：{source}")
    shutil.copy2(source, destination)


def sync_claude() -> int:
    """生成与真实源隔离的 Claude Code skill 副本。"""
    visible = _git_visible_files()
    names = set(skill_names(visible))
    managed = names | {"_shared"}
    _safe_generated_root(CLAUDE_ROOT)
    copied = 0
    # 先完整生成临时副本；复制失败时旧副本与用户额外条目都保持不变。
    with tempfile.TemporaryDirectory(prefix=".skills-stage-", dir=CLAUDE_ROOT.parent) as raw_stage:
        stage = Path(raw_stage)
        for rel in visible:
            parts = rel.parts
            if len(parts) < 3 or parts[0] != "skills":
                continue
            if parts[1] not in names and parts[1] != "_shared":
                continue
            source = REPO / rel
            destination = stage.joinpath(*parts[1:])
            _copy_entry(source, destination)
            copied += 1

        marker_text = (
            json.dumps(
                {
                    "generated_by": "scripts/sync_skill_entries.py",
                    "managed_top_level": sorted(managed),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n"
        )

        _install_claude_stage(stage, managed, marker_text)
    return copied


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_codex() -> list[str]:
    errors = []
    try:
        names = skill_names()
    except SyncError as exc:
        return [str(exc)]
    if not CODEX_ROOT.is_dir() or CODEX_ROOT.is_symlink():
        return [f"Codex skill 根目录缺失或类型错误：{CODEX_ROOT}"]
    for name in names:
        link = CODEX_ROOT / name
        expected = Path("..") / ".." / "skills" / name
        if not link.is_symlink():
            errors.append(f"Codex skill 入口缺失或不是链接：{link}")
        elif Path(os.readlink(link)) != expected:
            errors.append(f"Codex skill 链接目标错误：{link} -> {os.readlink(link)}")
        elif not (link / "SKILL.md").is_file():
            errors.append(f"Codex skill 链接不可用：{link}")
    return errors


def check_claude() -> list[str]:
    errors = []
    marker = CLAUDE_ROOT / CLAUDE_MARKER
    if not marker.is_file():
        return [f"Claude skill 副本未生成：{marker}"]
    try:
        visible = _git_visible_files()
        names = set(skill_names(visible))
    except SyncError as exc:
        return [str(exc)]
    expected_managed = names | {"_shared"}
    try:
        managed = _read_claude_managed_entries()
    except SyncError as exc:
        return [str(exc)]
    if managed != expected_managed:
        errors.append(
            f"Claude skill marker 条目过期：expected={sorted(expected_managed)}, actual={sorted(managed)}"
        )
    expected_files: dict[Path, Path] = {}
    for rel in visible:
        parts = rel.parts
        if len(parts) < 3 or parts[0] != "skills":
            continue
        if parts[1] in names or parts[1] == "_shared":
            expected_files[CLAUDE_ROOT.joinpath(*parts[1:])] = REPO / rel

    actual_files = set()
    for name in expected_managed:
        root = CLAUDE_ROOT / name
        if not root.exists():
            continue
        actual_files.update(path for path in root.rglob("*") if path.is_file() or path.is_symlink())
    if actual_files != set(expected_files):
        for path in sorted(set(expected_files) - actual_files):
            errors.append(f"Claude skill 副本缺文件：{path}")
        for path in sorted(actual_files - set(expected_files)):
            errors.append(f"Claude skill 副本有陈旧文件：{path}")

    for destination, source in expected_files.items():
        if destination not in actual_files:
            continue
        if source.is_symlink():
            if not destination.is_symlink() or os.readlink(destination) != os.readlink(source):
                errors.append(f"Claude skill 副本链接不一致：{destination}")
        elif destination.is_symlink() or _sha256(destination) != _sha256(source):
            errors.append(f"Claude skill 副本内容过期：{destination}")
    return errors


def check() -> None:
    errors = check_codex() + check_claude()
    if errors:
        for error in errors:
            print(f"[错误] {error}", file=sys.stderr)
        raise SystemExit(1)
    print(f"[通过] Codex/Claude skill 接线完整（{len(skill_names())} 个 skill）")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="只校验，不写入")
    args = parser.parse_args()
    try:
        if args.check:
            check()
            return
        codex_count = sync_codex()
        copied_count = sync_claude()
        print(f"[已同步] Codex 链接 {codex_count} 个；Claude 隔离副本 {copied_count} 个文件")
        check()
    except (OSError, subprocess.CalledProcessError, SyncError) as exc:
        print(f"[错误] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
