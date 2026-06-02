import sqlite3
import threading
from pathlib import Path

DB_PATH = Path(__file__).parent / "imoveis_bauru.db"
PAGE_SIZE = 20

_local = threading.local()

_COLS = (
    "InscrFisico", "NomeResponsavelTributario", "TipoResponsavelTributario",
    "CPFCNPJRespTrib", "EnderecoImovel", "CepImovel", "EnderecoCorresp",
    "AreaTerreno", "TotalAreaEdificada", "Finalidade",
    "TpConstrucao", "Categoria", "Conservacao",
    "ClassificacaoTributaria", "AnoConstrucao",
)


def _conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn"):
        conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA query_only = ON")
        conn.execute("PRAGMA cache_size = -32000")   # 32 MB cache
        conn.execute("PRAGMA mmap_size = 268435456") # 256 MB mmap
        _local.conn = conn
    return _local.conn


def search(q: str, page: int) -> tuple[list[dict], int]:
    if not q:
        return [], 0

    conn = _conn()
    offset = (page - 1) * PAGE_SIZE
    fts_q = _fts_query(q)
    cols = ", ".join(f"a.{c}" for c in _COLS)

    try:
        total = conn.execute(
            "SELECT COUNT(*) FROM imoveis_fts WHERE imoveis_fts MATCH ?",
            (fts_q,),
        ).fetchone()[0]

        rows = conn.execute(
            f"SELECT {cols} "
            f"FROM imoveis_fts "
            f"JOIN imoveis_agregado a ON imoveis_fts.rowid = a.rowid "
            f"WHERE imoveis_fts MATCH ? ORDER BY rank LIMIT ? OFFSET ?",
            (fts_q, PAGE_SIZE, offset),
        ).fetchall()

    except sqlite3.OperationalError:
        total, rows = _like_search(conn, q, offset)

    return [dict(r) for r in rows], total


def _fts_query(q: str) -> str:
    return " ".join(
        f'"{t.replace(chr(34), "")}"*'
        for t in q.split()
        if t
    )


def _like_search(conn: sqlite3.Connection, q: str, offset: int) -> tuple[int, list]:
    p = f"%{q}%"
    where = (
        "FROM imoveis_agregado "
        "WHERE EnderecoImovel LIKE ? OR CepImovel LIKE ? "
        "   OR InscrFisico LIKE ? OR NomeResponsavelTributario LIKE ?"
    )
    params = (p, p, p, p)
    cols = ", ".join(_COLS)
    total = conn.execute(f"SELECT COUNT(*) {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT {cols} {where} LIMIT ? OFFSET ?",
        params + (PAGE_SIZE, offset),
    ).fetchall()
    return total, rows
