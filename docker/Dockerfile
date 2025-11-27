# Cloud Custodian Azure Container Apps Runner
# マルチステージビルドで軽量イメージを作成

# ビルドステージ
FROM python:3.14-slim AS builder

WORKDIR /app

# ビルドに必要なパッケージをインストール
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# pip のアップグレード
RUN pip install --no-cache-dir --upgrade pip

# 依存関係のみを先にインストール（キャッシュ活用）
COPY pyproject.toml ./
RUN pip install --no-cache-dir build && \
    pip wheel --no-cache-dir --wheel-dir /wheels \
    c7n>=0.9.47 \
    c7n-azure>=0.7.46 \
    click>=8.1.0 \
    azure-identity>=1.15.0 \
    azure-storage-queue>=12.9.0 \
    azure-storage-blob>=12.19.0 \
    pyyaml>=6.0 \
    pydantic>=2.5.0

# アプリケーションコードをコピーしてビルド
COPY src/ ./src/
COPY README.md ./
RUN pip wheel --no-cache-dir --wheel-dir /wheels .

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

# ビルドステージから wheel をコピーしてインストール
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir /wheels/*.whl && \
    rm -rf /wheels

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
