#!/usr/bin/env bash
# Install every arm's tool once, at the version pinned in arms/versions.json.
#
#   BENCH_TOOLS   where to install (default $HOME/.cache/trust-me-bro/tools)
#                 binaries go to $BENCH_TOOLS/bin, python tools to $BENCH_TOOLS/venvs/<tool>
#
# Idempotent: a tool whose `--version` already reports the pinned version is skipped.
# Usage: arms/install.sh [arm ...]     (default: every arm)
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
VERSIONS="$HERE/versions.json"
BENCH_TOOLS=${BENCH_TOOLS:-$HOME/.cache/trust-me-bro/tools}
BIN="$BENCH_TOOLS/bin"
mkdir -p "$BIN" "$BENCH_TOOLS/venvs" "$BENCH_TOOLS/downloads"

field() { # field <arm> <key>  -> value from versions.json ("" when null/missing)
  python3 -I -c 'import json,sys
v = json.load(open(sys.argv[1]))["arms"][sys.argv[2]].get(sys.argv[3])
print("" if v is None else v)' "$VERSIONS" "$1" "$2"
}

has_version() { # has_version <binary path> <version>
  [ -x "$1" ] && "$1" --version 2>/dev/null | grep -qF "$2"
}

install_release() { # <arm> <expected --version text>: a GitHub release binary, sha256-checked
  local arm=$1 expected=$2 name version url sha tarball tmp found inside
  name=$(field "$arm" binary); version=$(field "$arm" version)
  # the binary's name in the archive, when it is installed under another name
  inside=$(field "$arm" archive_binary); [ -n "$inside" ] || inside=$name
  url=$(field "$arm" url); sha=$(field "$arm" sha256)
  if has_version "$BIN/$name" "$expected" && [ "$(sha256sum < "$BIN/$name")" = "$(cat "$BIN/.$name.sha256" 2>/dev/null)" ]; then
    echo "[$arm] $name $version already installed"; return 0
  fi
  tarball="$BENCH_TOOLS/downloads/$(basename "$url")"
  if [ ! -f "$tarball" ] || ! echo "$sha  $tarball" | sha256sum -c --quiet - 2>/dev/null; then
    echo "[$arm] downloading $url"
    curl -fsSL --retry 3 -o "$tarball.part" "$url"
    mv "$tarball.part" "$tarball"
  fi
  echo "$sha  $tarball" | sha256sum -c --quiet - || { echo "[$arm] checksum mismatch for $tarball" >&2; return 1; }
  tmp=$(mktemp -d)
  tar -xzf "$tarball" -C "$tmp"
  found=$(find "$tmp" -type f -name "$inside" -perm -u+x | head -n1)
  [ -n "$found" ] || { echo "[$arm] no $inside binary in $tarball" >&2; rm -rf "$tmp"; return 1; }
  install -m 0755 "$found" "$BIN/$name"
  sha256sum < "$BIN/$name" > "$BIN/.$name.sha256"
  rm -rf "$tmp"
}

install_pypi() { # <arm> <expected --version text>: a python tool in its own virtualenv, linked into $BIN
  local arm=$1 expected=$2 name version package extras python venv spec
  name=$(field "$arm" binary); version=$(field "$arm" version)
  package=$(field "$arm" package); extras=$(field "$arm" extras); python=$(field "$arm" python)
  venv="$BENCH_TOOLS/venvs/$name"
  spec="$package${extras:+[$extras]}==$version"
  # The extras are part of what is pinned: same version, other extras = reinstall.
  if has_version "$venv/bin/$name" "$expected" && [ "$(cat "$venv/.bench-spec" 2>/dev/null)" = "$spec" ]; then
    ln -sfn "$venv/bin/$name" "$BIN/$name"
    echo "[$arm] $spec already installed"; return 0
  fi
  echo "[$arm] installing $spec with python $python into $venv"
  rm -rf "$venv"
  if command -v uv >/dev/null 2>&1; then
    uv venv --quiet --python "$python" "$venv"
    uv pip install --quiet --python "$venv/bin/python" "$spec"
  else
    "python$python" -m venv "$venv"
    "$venv/bin/pip" install --quiet "$spec"
  fi
  echo "$spec" > "$venv/.bench-spec"
  ln -sfn "$venv/bin/$name" "$BIN/$name"
}

warm_headroom() { # fill the caches the proxy would otherwise download into on first use
  local venv="$BENCH_TOOLS/venvs/headroom" cache="$BENCH_TOOLS/cache/headroom"
  mkdir -p "$cache/hf" "$cache/tiktoken"
  # Kompress (headroom's ONNX text compressor) comes from the Hugging Face hub. Plain
  # HTTP downloads: the xet transfer hosts are blocked by some egress proxies.
  if HF_HOME="$cache/hf" HF_HUB_DISABLE_XET=1 "$venv/bin/python" -I -c '
import sys
from headroom.transforms.kompress_compressor import warm_kompress_model
sys.exit(0 if warm_kompress_model() else 1)' >/dev/null 2>&1; then
    echo "[headroom] Kompress model cached in $cache/hf"
  else
    echo "[headroom] WARNING: could not cache the Kompress model; the proxy will try to download it at run time" >&2
  fi
  # tiktoken vocabularies, used by headroom's token counter (it falls back to estimates).
  if TIKTOKEN_CACHE_DIR="$cache/tiktoken" timeout 120 "$venv/bin/python" -I -c '
import tiktoken
for name in ("cl100k_base", "o200k_base", "p50k_base"):
    tiktoken.get_encoding(name)' >/dev/null 2>&1; then
    echo "[headroom] tiktoken vocabularies cached in $cache/tiktoken"
  else
    echo "[headroom] WARNING: could not cache tiktoken vocabularies (openaipublic.blob.core.windows.net unreachable?); headroom will estimate token counts" >&2
  fi
}

check_glibc() { # the lean-ctx gnu build is what its installer picks on glibc >= 2.35
  local v
  v=$(ldd --version 2>&1 | head -n1 | grep -oE '[0-9]+\.[0-9]+$' || true)
  python3 -I -c 'import sys; a,b = map(int, sys.argv[1].split(".")); sys.exit(0 if (a,b) >= (2,35) else 1)' "${v:-0.0}" \
    || { echo "lean-ctx: glibc >= 2.35 required for the pinned gnu build (found ${v:-unknown})" >&2; return 1; }
}

install_arm() {
  local arm=$1 source name version expected
  source=$(field "$arm" source)
  # what `--version` prints: the version, unless versions.json says otherwise
  expected=$(field "$arm" version_output); [ -n "$expected" ] || expected=$(field "$arm" version)
  case "$source" in
    "") echo "[$arm] nothing to install"; return 0 ;;
    github-release) [ "$arm" = lean-ctx ] && check_glibc; install_release "$arm" "$expected" ;;
    pypi) install_pypi "$arm" "$expected" ;;
    *) echo "[$arm] unknown source '$source'" >&2; return 1 ;;
  esac
  [ "$arm" = headroom ] && warm_headroom
  name=$(field "$arm" binary)
  echo "[$arm] $("$BIN/$name" --version 2>&1 | head -n1)"
  has_version "$BIN/$name" "$expected" || { echo "[$arm] $name --version does not report '$expected'" >&2; return 1; }
}

arms=("$@")
if [ ${#arms[@]} -eq 0 ]; then
  mapfile -t arms < <(python3 -I -c 'import json,sys; print("\n".join(json.load(open(sys.argv[1]))["arms"]))' "$VERSIONS")
fi

failed=0
for arm in "${arms[@]}"; do
  install_arm "$arm" || { echo "[$arm] INSTALL FAILED" >&2; failed=1; }
done
exit $failed
