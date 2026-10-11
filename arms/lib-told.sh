# The user-level CLAUDE.md of the "-told" arms: a user who connected a tool tells the agent
# when to use it. Source it after lib.sh; write_told <native|sobre|sobre-dense>.
write_told() {
  mkdir -p "$CLAUDE_CONFIG_DIR"
  case "$1" in
    native) cat > "$CLAUDE_CONFIG_DIR/CLAUDE.md" <<'MD'
# Memory

Save what a later session would need (findings, decisions, the files and commits involved) to your memory as you go, and check your memory at the start of a session.
MD
    ;;
    sobre) cat > "$CLAUDE_CONFIG_DIR/CLAUDE.md" <<'MD'
# sobre

sobre's MCP tools are connected; they load through tool search.

- To find where a behaviour lives when you do not know the code's words, use `sobre_search` with `action="semantic"` and a plain-language query.
- Record what you find and decide with `sobre_session` (`action="finding"`, `action="decision"`) as you go. At the start of a session, call `sobre_session` with `action="load"` to see what earlier sessions found.
MD
    ;;
    sobre-dense) cat > "$CLAUDE_CONFIG_DIR/CLAUDE.md" <<'MD'
# sobre

sobre's MCP tools are connected; they load through tool search. This build has local embeddings.

- To find where a behaviour lives when you do not know the code's words, use `sobre_search` with `action="semantic"`, `mode="hybrid"` and a plain-language query.
- Record what you find and decide with `sobre_session` (`action="finding"`, `action="decision"`) as you go. At the start of a session, call `sobre_session` with `action="load"` to see what earlier sessions found.
MD
    ;;
    *) echo "write_told: unknown kind $1" >&2; return 1 ;;
  esac
}
