# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
"""
エントリポイントモジュール

コンテナ起動時のメインエントリポイント
"""

from __future__ import annotations

import logging
import os
import sys

log = logging.getLogger(__name__)


def detect_execution_mode() -> str:
    """
    環境変数から実行モードを自動検出

    Returns:
        実行モード ("event", "scheduled", "single")
    """
    # 明示的なモード指定
    explicit_mode = os.environ.get("C7N_EXECUTION_MODE", "").lower()
    if explicit_mode in ("event", "scheduled", "single"):
        return explicit_mode

    # イベントデータが渡されている場合
    if os.environ.get("C7N_EVENT_DATA"):
        return "event"

    # Queue 設定がある場合
    queue_storage_account = os.environ.get("AZURE_QUEUE_STORAGE_ACCOUNT") or os.environ.get(
        "C7N_STORAGE_ACCOUNT"
    )
    queue_name = os.environ.get("AZURE_QUEUE_NAME") or os.environ.get("C7N_QUEUE_NAME")
    if queue_storage_account and queue_name:
        return "event"

    # ポリシーファイルが直接指定されている場合
    if os.environ.get("C7N_POLICY_FILE"):
        return "single"

    # デフォルトは scheduled
    return "scheduled"


def main() -> None:
    """
    メインエントリポイント

    環境変数に基づいて適切なモードでポリシーを実行します。
    """
    from c7n_azure_container_apps.cli import main as cli_main

    mode = detect_execution_mode()
    log.info(f"Detected execution mode: {mode}")

    # CLI コマンドを構築
    if mode == "event":
        sys.argv = [sys.argv[0], "run-event"]
    elif mode == "scheduled":
        sys.argv = [sys.argv[0], "run-scheduled"]
    else:
        sys.argv = [sys.argv[0], "run-policy"]

    # CLI を実行
    cli_main()


if __name__ == "__main__":
    main()
