# Cloud Custodian Azure Container Apps Runner
# マルチステージビルドで軽量イメージを作成

# ビルドステージ
FROM python:3.14-slim AS builder

# uv をインストール
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# ビルドに必要なパッケージをインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# ロックファイルと設定をコピー（キャッシュ活用のためソースコードより先）
COPY pyproject.toml uv.lock README.md ./

# ロックファイルから依存関係のみを仮想環境へインストール（アプリ本体は除く）
RUN uv sync --frozen --no-dev --no-install-project

# アプリケーションコードをコピーしてインストール
COPY src/ ./src/
RUN uv sync --frozen --no-dev

# 実行ステージ
FROM python:3.14-slim AS runtime

# セキュリティ: 非 root ユーザーで実行
RUN groupadd --gid 1000 c7n && \
    useradd --uid 1000 --gid c7n --shell /bin/bash --create-home c7n

WORKDIR /app

# ランタイムに必要な最小限のパッケージ
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ビルドステージから仮想環境をコピー
COPY --from=builder /app/.venv /app/.venv

# 仮想環境を有効化
ENV PATH="/app/.venv/bin:$PATH"

# 出力ディレクトリを作成
RUN mkdir -p /tmp/c7n-output && chown c7n:c7n /tmp/c7n-output

# 非 root ユーザーに切り替え
USER c7n

# 環境変数のデフォルト値
ENV AZURE_OUTPUT_DIR=/tmp/c7n-output \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# ヘルスチェック用（オプション）
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import c7n_azure_runner; print('OK')" || exit 1

# エントリポイント
ENTRYPOINT ["python", "-m", "c7n_azure_container_apps.entrypoint"]

# ラベル
LABEL org.opencontainers.image.title="Cloud Custodian Azure Container Apps Runner" \
      org.opencontainers.image.description="Run Cloud Custodian policies in Azure Container Apps Jobs" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.source="https://github.com/fukasawah/az-c7n-azure-container-apps"
