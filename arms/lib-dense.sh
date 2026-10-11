# The local-embeddings model and ONNX Runtime for the -dense arms, downloaded once by
# `sobre embeddings provision` into a home under $BENCH_TOOLS/cache (provision_dense), then
# linked into each run's fresh HOME (link_dense). Source it after lib.sh.
DENSE_HOME="$BENCH_TOOLS/cache/sobre-dense-home"

provision_dense() { # provision_dense <sobre dense binary>
  if [ ! -d "$DENSE_HOME/.cache/sobre/models" ] || [ -z "$(find "$DENSE_HOME/.local/share/sobre/onnxruntime" -name 'libonnxruntime*' 2>/dev/null | head -n1)" ]; then
    mkdir -p "$DENSE_HOME"
    HOME="$DENSE_HOME" "$1" embeddings provision </dev/null >&2
  fi
}

link_dense() { # link the shared model into this HOME; print the ONNX Runtime library's path
  local ort
  mkdir -p "$HOME/.cache/sobre"
  ln -sfn "$DENSE_HOME/.cache/sobre/models" "$HOME/.cache/sobre/models"
  ort=$(find "$DENSE_HOME/.local/share/sobre/onnxruntime" -name 'libonnxruntime*.so*' -type f | head -n1)
  [ -n "$ort" ] || { echo "no ONNX Runtime under $DENSE_HOME" >&2; return 1; }
  echo "$ort"
}
