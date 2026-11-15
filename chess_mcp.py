#!/usr/bin/env python3
"""
chess_mcp.py — a tiny MCP server that lets a Claude client play a REAL game of
chess against Stockfish.

The design keeps the match fair: the server owns the board and the engine.
Claude picks its OWN moves (no engine help); Stockfish answers each one. Claude
never gets to "see" Stockfish's analysis for its own move — it only gets the
position, the legal moves, and an objective evaluation for context.

Tools exposed to the client:
  - new_game(color, elo)  -> start a fresh game; you choose your side + SF strength
  - get_board()           -> current position (board art + FEN + legal SAN moves + eval)
  - play_move(san)        -> play YOUR move in SAN; Stockfish replies automatically
  - pgn()                 -> the whole game so far as PGN (paste into lichess.org/paste)

Requirements:  pip install chess mcp        and a `stockfish` binary on PATH
               (set STOCKFISH_PATH to override the binary location).

Register it with Claude Desktop in claude_desktop_config.json — see
claude_desktop_config.example.json in this folder — then restart the app.
"""

import os
import chess
import chess.engine
import chess.pgn
import datetime

from mcp.server.fastmcp import FastMCP

# `brew install stockfish` puts the binary on PATH as "stockfish".
STOCKFISH_PATH = os.environ.get("STOCKFISH_PATH", "stockfish")

mcp = FastMCP("chess")

# Single in-memory game. (One game at a time is plenty for a desktop match.)
STATE = {
    "board": None,          # chess.Board
    "elo": 1500,            # Stockfish strength
    "claude_color": chess.WHITE,
    "move_times": 0.30,     # seconds Stockfish thinks per reply
    "eval_depth": 12,       # depth for the *objective* (full-strength) eval
}


# ----------------------------------------------------------------------------- helpers

def _open_engine():
    return chess.engine.SimpleEngine.popen_uci(STOCKFISH_PATH)


def _objective_eval(board):
    """A FULL-STRENGTH eval of the position (White's point of view), independent
    of the weakened opponent. Returns e.g. '+1.35' or '#4' (mate in 4)."""
    with _open_engine() as eng:
        info = eng.analyse(board, chess.engine.Limit(depth=STATE["eval_depth"]))
        score = info["score"].white()
        if score.is_mate():
            return f"#{score.mate()}"
        return f"{score.score() / 100:+.2f}"


def _stockfish_reply():
    """Let the (Elo-limited) Stockfish make Black/White's reply. Returns SAN or None."""
    board = STATE["board"]
    if board.is_game_over():
        return None
    with _open_engine() as eng:
        eng.configure({"UCI_LimitStrength": True, "UCI_Elo": STATE["elo"]})
        result = eng.play(board, chess.engine.Limit(time=STATE["move_times"]))
    san = board.san(result.move)
    board.push(result.move)
    return san


def _render():
    board = STATE["board"]
    lines = [board.unicode(invert_color=True, borders=False), "FEN: " + board.fen()]
    if board.is_game_over():
        term = str(board.outcome().termination).split(".")[-1]
        lines.append(f"GAME OVER: {board.result()} ({term})")
    else:
        lines.append("To move: " + ("White" if board.turn else "Black"))
        legal = sorted(board.san(m) for m in board.legal_moves)
        lines.append(f"Legal moves (SAN): {' '.join(legal)}")
    try:
        lines.append("Objective eval (White POV, pawns): " + _objective_eval(board))
    except Exception as exc:  # engine missing / busy — don't block the game
        lines.append(f"(eval unavailable: {exc})")
    return "\n".join(lines)


# ----------------------------------------------------------------------------- tools

@mcp.tool()
def new_game(color: str = "white", elo: int = 1500) -> str:
    """Start a new game.

    color: the side YOU (the model) play — 'white' or 'black'.
    elo:   Stockfish's strength, 1320-3190 (it is capped to that range).
    If you choose black, Stockfish (white) makes the opening move immediately.
    """
    STATE["board"] = chess.Board()
    STATE["claude_color"] = chess.WHITE if color.lower().startswith("w") else chess.BLACK
    STATE["elo"] = max(1320, min(3190, int(elo)))
    header = f"New game — you are {('White' if STATE['claude_color'] else 'Black')} " \
             f"vs Stockfish @{STATE['elo']} Elo."
    if STATE["claude_color"] == chess.BLACK:
        first = _stockfish_reply()
        if first:
            header += f"  Stockfish opened with {first}."
    return header + "\n" + _render()


@mcp.tool()
def get_board() -> str:
    """Return the current position: board art, FEN, the legal moves in SAN, and an
    objective (full-strength Stockfish) evaluation. Call this before every move,
    think it through, then call play_move."""
    if STATE["board"] is None:
        return "No game in progress. Call new_game first."
    return _render()


@mcp.tool()
def play_move(san: str) -> str:
    """Play YOUR move, in Standard Algebraic Notation (e.g. 'Nf3', 'exd5', 'O-O',
    'e8=Q+'). The move is validated for legality; then Stockfish replies
    automatically and the new position is returned."""
    board = STATE["board"]
    if board is None:
        return "No game in progress. Call new_game first."
    try:
        move = board.parse_san(san)
    except Exception as exc:
        legal = " ".join(sorted(board.san(m) for m in board.legal_moves))
        return f"'{san}' is not a legal move here ({exc}).\nLegal moves: {legal}"

    played = board.san(move)
    board.push(move)
    out = [f"You played: {played}"]
    if not board.is_game_over():
        reply = _stockfish_reply()
        if reply:
            out.append(f"Stockfish(@{STATE['elo']}) replied: {reply}")
    out.append("---")
    out.append(_render())
    return "\n".join(out)


@mcp.tool()
def pgn() -> str:
    """Return the whole game so far as PGN (paste it into lichess.org/paste to replay)."""
    board = STATE["board"]
    if board is None:
        return "No game in progress."
    game = chess.pgn.Game()
    game.headers["Event"] = "Claude vs Stockfish"
    game.headers["White"] = "Claude" if STATE["claude_color"] == chess.WHITE else f"Stockfish @{STATE['elo']}"
    game.headers["Black"] = f"Stockfish @{STATE['elo']}" if STATE["claude_color"] == chess.WHITE else "Claude"
    game.headers["Date"] = datetime.date.today().strftime("%Y.%m.%d")
    node = game
    replay = chess.Board()
    for mv in board.move_stack:
        node = node.add_variation(mv)
        replay.push(mv)
    if board.is_game_over():
        game.headers["Result"] = board.result()
    return str(game)


if __name__ == "__main__":
    # Speaks MCP over stdio — this is how Claude Desktop launches it.
    mcp.run()
