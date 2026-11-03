#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
ENV_DIR="$ROOT/manimgl_env"
UV_BIN="${UV_BIN:-$HOME/.local/bin/uv}"

if [[ ! -x "$UV_BIN" ]]; then
  installer="${TMPDIR:-/tmp}/manimind-uv-install.sh"
  curl --proto '=https' --tlsv1.2 -LsSf https://astral.sh/uv/install.sh -o "$installer"
  sh "$installer"
fi

if [[ ! -x "$ENV_DIR/bin/python" ]]; then
  "$UV_BIN" venv --python 3.12 --seed "$ENV_DIR"
fi
"$UV_BIN" pip install \
  --python "$ENV_DIR/bin/python" \
  -e "${ROOT}[dev,api,llm,pdf,render]"

MANIMIND_ENV_DIR="$ENV_DIR" "$ENV_DIR/bin/python" - <<'PY'
import os
from pathlib import Path
from static_ffmpeg import run

bin_dir = Path(os.environ["MANIMIND_ENV_DIR"]) / "bin"
ffmpeg, ffprobe = run.get_or_fetch_platform_executables_else_raise()
for name, source in (("ffmpeg", ffmpeg), ("ffprobe", ffprobe)):
    link = bin_dir / name
    link.unlink(missing_ok=True)
    link.symlink_to(source)
PY

TEX_ROOT="${TINYTEX_DIR:-$HOME/Library/TinyTeX}"
TEX_BIN="$(find "$TEX_ROOT/bin" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | head -1 || true)"
if [[ -z "$TEX_BIN" || ! -x "$TEX_BIN/tlmgr" ]]; then
  archive="${TMPDIR:-/tmp}/TinyTeX-1-darwin.tar.xz"
  curl -L --fail --retry 5 \
    https://github.com/rstudio/tinytex-releases/releases/download/daily/TinyTeX-1-darwin.tar.xz \
    -o "$archive"
  mkdir -p "$(dirname "$TEX_ROOT")"
  tar xf "$archive" -C "$(dirname "$TEX_ROOT")"
  TEX_BIN="$(find "$TEX_ROOT/bin" -mindepth 1 -maxdepth 1 -type d | head -1)"
fi

"$TEX_BIN/tlmgr" postaction install script xetex
"$TEX_BIN/tlmgr" install \
  dvisvgm ctex standalone preview doublestroke relsize fundus-calligra wasysym physics
ln -sfn "$TEX_BIN/xelatex" "$ENV_DIR/bin/xelatex"
ln -sfn "$TEX_BIN/dvisvgm" "$ENV_DIR/bin/dvisvgm"

if [[ ! -x "$ENV_DIR/bin/node" ]]; then
  if ! command -v node >/dev/null 2>&1; then
    if [[ ! -s "$HOME/.nvm/nvm.sh" ]]; then
      nvm_installer="${TMPDIR:-/tmp}/manimind-nvm-install.sh"
      curl --proto '=https' --tlsv1.2 -LsSf \
        https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.3/install.sh \
        -o "$nvm_installer"
      PROFILE=/dev/null NVM_DIR="$HOME/.nvm" bash "$nvm_installer"
    fi
    set +u
    export NVM_DIR="$HOME/.nvm"
    source "$NVM_DIR/nvm.sh"
    nvm install --lts
    set -u
  fi
  node_dir="$(dirname "$(command -v node)")"
  for tool in node npm npx corepack; do
    [[ -x "$node_dir/$tool" ]] && ln -sfn "$node_dir/$tool" "$ENV_DIR/bin/$tool"
  done
fi

if [[ ! -x "$ENV_DIR/bin/bun" ]]; then
  if [[ ! -x "$HOME/.bun/bin/bun" ]]; then
    bun_installer="${TMPDIR:-/tmp}/manimind-bun-install.sh"
    curl --proto '=https' --tlsv1.2 -LsSf https://bun.com/install -o "$bun_installer"
    bash "$bun_installer"
  fi
  ln -sfn "$HOME/.bun/bin/bun" "$ENV_DIR/bin/bun"
fi

[[ -f "$ROOT/.env" ]] && chmod 600 "$ROOT/.env"
PATH="$ENV_DIR/bin:$PATH" "$ENV_DIR/bin/python" -m manimind.main doctor \
  | tee "$ROOT/runtime/doctor-report.json"

printf '\nManiMind macOS environment is ready.\n'
printf 'Activate it with: source %s/bin/activate\n' "$ENV_DIR"
