import sys, json, os, chess, chess.pgn, chess.engine, io, datetime

SF = os.environ.get("STOCKFISH_PATH", "stockfish")  # originally /home/claude/Stockfish/src/stockfish (cloud run)
GDIR = os.environ.get("GAME_DIR", os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_state"))  # originally /home/claude/game

os.makedirs(GDIR, exist_ok=True)

def state_path(gid): return os.path.join(GDIR, f"{gid}.json")

def load(gid):
    with open(state_path(gid)) as f: return json.load(f)

def save(gid, st):
    with open(state_path(gid), "w") as f: json.dump(st, f)

def board_from(st):
    b = chess.Board()
    for m in st["moves"]:
        b.push_san(m)
    return b

def objective_eval(board):
    # full-strength analysis, white's POV, centipawns
    with chess.engine.SimpleEngine.popen_uci(SF) as eng:
        info = eng.analyse(board, chess.engine.Limit(depth=12))
        sc = info["score"].white()
        if sc.is_mate():
            m = sc.mate()
            return {"mate": m, "cp": None}
        return {"mate": None, "cp": sc.score()}

def render(board, st, last_eval):
    out = []
    out.append(board.unicode(invert_color=True, borders=False))
    out.append("FEN: " + board.fen())
    out.append("Move #: %d, to move: %s" % (board.fullmove_number, "White(you)" if board.turn else "Black(SF)"))
    ev = last_eval
    if ev:
        if ev["mate"] is not None:
            out.append("Objective eval (White POV): mate in %d" % ev["mate"])
        else:
            out.append("Objective eval (White POV): %+d cp (%+.2f pawns)" % (ev["cp"], ev["cp"]/100))
    if board.is_game_over():
        out.append("GAME OVER: " + board.result() + " (" + str(board.outcome().termination).split('.')[-1] + ")")
    else:
        legal = sorted(board.san(m) for m in board.legal_moves)
        out.append("Legal moves (%d): %s" % (len(legal), " ".join(legal)))
    return "\n".join(out)

def cmd_new(gid, elo):
    st = {"elo": int(elo), "moves": [], "evals": []}
    save(gid, st)
    b = chess.Board()
    print(render(b, st, None))

def cmd_mymove(gid, san):
    st = load(gid)
    b = board_from(st)
    # my move
    mv = b.parse_san(san)   # raises on illegal
    real_san = b.san(mv)
    b.push(mv)
    st["moves"].append(real_san)
    ev1 = objective_eval(b)
    st["evals"].append(ev1)
    print("You played: %s" % real_san)
    if not b.is_game_over():
        # stockfish reply at limited strength
        with chess.engine.SimpleEngine.popen_uci(SF) as eng:
            eng.configure({"UCI_LimitStrength": True, "UCI_Elo": st["elo"]})
            res = eng.play(b, chess.engine.Limit(time=0.30))
        sf_san = b.san(res.move)
        b.push(res.move)
        st["moves"].append(sf_san)
        ev2 = objective_eval(b)
        st["evals"].append(ev2)
        print("Stockfish(%d) replied: %s" % (st["elo"], sf_san))
        last = ev2
    else:
        last = ev1
    save(gid, st)
    print("---")
    print(render(b, st, last))

def cmd_pgn(gid):
    st = load(gid)
    b = chess.Board()
    g = chess.pgn.Game()
    g.headers["Event"] = "Claude vs Stockfish ladder"
    g.headers["White"] = "Claude (Opus 4.8)"
    g.headers["Black"] = "Stockfish @%d Elo" % st["elo"]
    g.headers["Date"] = datetime.date.today().strftime("%Y.%m.%d")
    node = g
    tmp = chess.Board()
    for m in st["moves"]:
        mv = tmp.push_san(m)
        node = node.add_variation(mv)
    if tmp.is_game_over():
        g.headers["Result"] = tmp.result()
    print(str(g))
    print("\nEVALS(cp White POV per half-move):")
    print([ (e["cp"] if e["cp"] is not None else ("M%d"%e["mate"])) for e in st["evals"] ])

if __name__ == "__main__":
    c = sys.argv[1]
    if c == "new": cmd_new(sys.argv[2], sys.argv[3])
    elif c == "mymove": cmd_mymove(sys.argv[2], sys.argv[3])
    elif c == "pgn": cmd_pgn(sys.argv[2])
