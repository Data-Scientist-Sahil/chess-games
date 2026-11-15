# chess-games — Claude vs Stockfish

Everything from the "play Stockfish against Claude" experiment, plus a proper
MCP server so your **Claude Desktop** app can play real games itself.

> **Honesty note on where it ran.** The original 4-game ladder (1350 → 1800 →
> 2200 → 2600) was **not** run on your Mac. It ran in a cloud Linux workspace,
> where I (Claude) drove a small UCI harness move-by-move and a from-source
> Stockfish answered. That harness (`engine_game.py`) is included here exactly
> as used. The `chess_mcp.py` server is the thing you originally asked about —
> it lets your *desktop* app play — and is new in this folder. The Stockfish
> binary from the cloud run was a **Linux x86-64** build and will not run on
> macOS, so it is intentionally **not** copied here; `setup.sh` installs the
> correct macOS build via Homebrew.

---

## Contents

| File | What it is |
|---|---|
| `chess_mcp.py` | **The MCP server.** Tools: `new_game`, `get_board`, `play_move`, `pgn`. Owns the board + Stockfish so the match is fair. |
| `engine_game.py` | The CLI harness used for the actual ladder. Subcommands: `new <id> <elo>`, `mymove <id> <SAN>`, `pgn <id>`. State persisted to `<id>.json`. |
| `requirements.txt` | Python deps: `chess`, `mcp`. |
| `setup.sh` | One-time macOS setup: `brew install stockfish` + a `venv` with the deps. |
| `claude_desktop_config.example.json` | The `mcpServers` snippet to paste into your real Claude Desktop config. |
| `evals.json` | Per-move objective evals (centipawns, White POV) + blunder markers for all 4 games. |
| `games/*.pgn` | The four games. Paste any into <https://lichess.org/paste> to replay. |

---

## Quick start (macOS)

```bash
cd chess-games
chmod +x setup.sh
./setup.sh                 # installs stockfish + builds ./venv
```

### A) Let Claude Desktop play (the MCP server)

1. Open your Claude Desktop config:
   `~/Library/Application Support/Claude/claude_desktop_config.json`
2. Merge in the `chess` server from `claude_desktop_config.example.json`,
   replacing `/ABSOLUTE/PATH/TO/chess-games` with this folder's real path and
   pointing `command` at `./venv/bin/python`.
3. Fully quit and reopen Claude Desktop.
4. In a chat, say:
   > Start a new game as White vs Stockfish at 1500 Elo. Before each move call
   > `get_board`, think it through, then call `play_move`. Keep going until the
   > game ends. Don't ask me anything between moves.

`STOCKFISH_PATH` defaults to `stockfish` (on PATH after `brew install`). Override
it in the config `env` if your binary lives elsewhere.

### B) Reproduce the ladder yourself (the CLI harness)

```bash
source venv/bin/activate
python engine_game.py new mygame 1500      # new game vs Stockfish @1500, you are White
python engine_game.py mymove mygame e4     # you play e4; Stockfish replies; prints board + eval
python engine_game.py mymove mygame Nf3
python engine_game.py pgn mygame           # dump the PGN so far
```

The harness uses **two** engine instances on purpose: an Elo-limited one to make
the opponent's moves, and a separate full-strength one (depth 12) to score each
position objectively — that's where `evals.json` comes from.

---

## The result (tl;dr)

Claude lost all four games, but the engine's strength was barely the reason: in
every game Claude reached an equal-or-winning position (**+9** vs the 1350!) and
then lost it in a **single move**. Opening play was sound every time; each loss
came from one move that looked right but skipped a concrete tactical check (an
undefended fork square, a pawn capture, a pin). See `evals.json` for the exact
cliff in each game.

Why: an LLM plays from pattern recognition over text (great intuition, strongest
in the heavily-recorded opening) but is an unreliable *verifier* of the one
concrete line that refutes a plausible move. Pair it with a checker — in chess,
literally Stockfish — and you get the best of both.
