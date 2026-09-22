#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""安全更新 BCC Skill 到 GitHub 最新 Release。

用法：
  python scripts/update.py --check       # 仅检查本地与远端版本
  python scripts/update.py               # 下载并安装最新版本
  python scripts/update.py --dry-run     # 下载前只显示计划

更新时保留本机私有数据：data/Corpus、data/CorpusIdx、app/config、venv。
远端包必须是 GitHub Release 中名为 bcc-corpus.zip 的附件，且 ZIP 内只能
包含一个 bcc-corpus/ 顶层目录。更新器不会执行下载包中的任何脚本。
"""

import argparse
import json
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile

REPOSITORY = "stellaliu0104/bcc-corpus-skill"
API_URL = f"https://api.github.com/repos/{REPOSITORY}/releases/latest"
ASSET_NAME = "bcc-corpus.zip"
HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_ROOT = os.path.dirname(HERE)
VERSION_FILE = os.path.join(SKILL_ROOT, "VERSION")
PRESERVED = ("data/Corpus", "data/CorpusIdx", "app/config", "venv")
PROGRAM_EXCLUDES = {"data", "venv", ".git", "__pycache__"}


def emit(payload, exit_code=0):
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    raise SystemExit(exit_code)


def local_version():
    try:
        with open(VERSION_FILE, encoding="utf-8") as f:
            return f.read().strip() or "unknown"
    except OSError:
        return "unknown"


def fetch_release():
    request = urllib.request.Request(
        API_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "bcc-corpus-skill-updater",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            release = json.load(response)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        emit({
            "ok": False,
            "stage": "check_release",
            "error": "无法读取 GitHub 最新发行版。",
            "detail": str(exc),
            "hint": "请检查网络/代理，或稍后重试；不会修改本地文件。",
        }, 1)

    for asset in release.get("assets", []):
        if asset.get("name") == ASSET_NAME and asset.get("browser_download_url"):
            return release, asset
    emit({
        "ok": False,
        "stage": "check_release",
        "error": f"最新 Release 未找到 {ASSET_NAME} 附件。",
        "release": release.get("tag_name"),
        "hint": "请联系维护者在 GitHub Release 上传 bcc-corpus.zip；不会修改本地文件。",
    }, 1)


def release_version(release):
    return str(release.get("tag_name") or release.get("name") or "unknown").lstrip("v")


def download_asset(asset, destination):
    request = urllib.request.Request(
        asset["browser_download_url"],
        headers={"Accept": "application/octet-stream", "User-Agent": "bcc-corpus-skill-updater"},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response, open(destination, "wb") as out:
            shutil.copyfileobj(response, out)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as exc:
        emit({
            "ok": False,
            "stage": "download",
            "error": "下载更新包失败。",
            "detail": str(exc),
            "hint": "请检查网络后重试；不会修改本地文件。",
        }, 1)


def safe_members(archive):
    """验证归档结构，防 Zip Slip 和非预期顶层目录。"""
    root = "bcc-corpus/"
    members = archive.infolist()
    if not members:
        raise ValueError("更新包为空")
    for member in members:
        name = member.filename.replace("\\", "/")
        if name.startswith("/") or ".." in name.split("/"):
            raise ValueError(f"更新包包含不安全路径: {member.filename}")
        if not name.startswith(root) or name == root:
            raise ValueError("更新包必须只包含 bcc-corpus/ 顶层目录")
    return members


def unpack_program(zip_path, staging):
    try:
        with zipfile.ZipFile(zip_path) as archive:
            for member in safe_members(archive):
                rel = member.filename.replace("\\", "/").removeprefix("bcc-corpus/")
                if not rel or rel.split("/", 1)[0] in PROGRAM_EXCLUDES:
                    continue
                target = os.path.join(staging, *rel.split("/"))
                if member.is_dir():
                    os.makedirs(target, exist_ok=True)
                    continue
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with archive.open(member) as source, open(target, "wb") as destination:
                    shutil.copyfileobj(source, destination)
    except (OSError, zipfile.BadZipFile, ValueError) as exc:
        emit({
            "ok": False,
            "stage": "validate_package",
            "error": "更新包校验或解压失败。",
            "detail": str(exc),
            "hint": "不会修改本地文件；请联系维护者重新发布安装包。",
        }, 1)
    if not os.path.isfile(os.path.join(staging, "VERSION")):
        emit({
            "ok": False,
            "stage": "validate_package",
            "error": "更新包缺少 VERSION，已拒绝安装。",
            "hint": "请联系维护者重新发布安装包；不会修改本地文件。",
        }, 1)


def remove_path(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    elif os.path.exists(path):
        os.remove(path)


def replace_program(staging):
    backup = tempfile.mkdtemp(prefix="bcc-update-backup-", dir=os.path.dirname(SKILL_ROOT))
    saved_config = os.path.join(backup, "preserved", "app", "config")
    config_path = os.path.join(SKILL_ROOT, "app", "config")
    replaced = []
    config_saved = False
    try:
        # app 会整体替换，故先单独移走其中的本地设置，再在新 app 下恢复。
        if os.path.exists(config_path):
            os.makedirs(os.path.dirname(saved_config), exist_ok=True)
            shutil.move(config_path, saved_config)
            config_saved = True

        # 先备份与替换程序顶层条目；明确跳过用户数据和本地环境。
        for name in os.listdir(staging):
            source = os.path.join(staging, name)
            target = os.path.join(SKILL_ROOT, name)
            backup_target = os.path.join(backup, name)
            if os.path.exists(target):
                shutil.move(target, backup_target)
            shutil.move(source, target)
            replaced.append(name)

        if config_saved:
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            shutil.move(saved_config, config_path)
    except OSError as exc:
        # 尽最大可能回滚，避免半更新状态。
        for name in reversed(replaced):
            target = os.path.join(SKILL_ROOT, name)
            if os.path.exists(target):
                remove_path(target)
            backup_target = os.path.join(backup, name)
            if os.path.exists(backup_target):
                shutil.move(backup_target, target)
        if config_saved and os.path.exists(saved_config):
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            shutil.move(saved_config, config_path)
        emit({
            "ok": False,
            "stage": "install",
            "error": "替换程序文件失败，已尝试回滚。",
            "detail": str(exc),
            "hint": "请关闭正在运行的 Streamlit/检索任务后重试。",
        }, 1)
    finally:
        shutil.rmtree(backup, ignore_errors=True)
    return replaced


def main():
    parser = argparse.ArgumentParser(description="更新 BCC Skill 到 GitHub 最新 Release")
    parser.add_argument("--check", action="store_true", help="仅检查版本")
    parser.add_argument("--dry-run", action="store_true", help="仅显示更新计划")
    args = parser.parse_args()

    current = local_version()
    release, asset = fetch_release()
    latest = release_version(release)
    base = {
        "ok": True,
        "repository": REPOSITORY,
        "current_version": current,
        "latest_version": latest,
        "release_url": release.get("html_url"),
        "update_available": current != latest,
        "preserved": list(PRESERVED),
    }
    if args.check:
        emit(base)
    if current == latest:
        emit({**base, "updated": False, "message": "当前已是最新版本。"})
    if args.dry_run:
        emit({**base, "updated": False, "message": "将下载并替换程序文件；不会覆盖用户数据。"})

    with tempfile.TemporaryDirectory(prefix="bcc-update-") as temp:
        archive_path = os.path.join(temp, ASSET_NAME)
        staging = os.path.join(temp, "program")
        os.makedirs(staging)
        download_asset(asset, archive_path)
        unpack_program(archive_path, staging)
        installed_version = open(os.path.join(staging, "VERSION"), encoding="utf-8").read().strip()
        replaced = replace_program(staging)

    emit({
        **base,
        "latest_version": installed_version or latest,
        "updated": True,
        "replaced": replaced,
        "message": "更新完成。建议运行一次检索确认功能可用。",
    })


if __name__ == "__main__":
    main()
