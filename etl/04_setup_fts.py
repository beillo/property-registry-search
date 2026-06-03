#!/usr/bin/env python3
"""ETL step 4: build FTS5 full-text index. Run once locally, then compress."""
import sqlite3, sys, time
from pathlib import Path

DB = Path(__file__).parent.parent / "imoveis_bauru.db"

print(f"Conectando em {DB}…")
con = sqlite3.connect(str(DB))

exists = con.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name='imoveis_fts'"
).fetchone()
if exists:
    print("FTS5 já existe. Nada a fazer.")
    con.close()
    sys.exit(0)

t = time.perf_counter()

print("Criando tabela virtual FTS5…")
con.execute("""
    CREATE VIRTUAL TABLE imoveis_fts USING fts5(
        InscrFisico,
        NomeResponsavelTributario,
        EnderecoImovel,
        CepImovel,
        content='imoveis_agregado',
        tokenize='unicode61 remove_diacritics 1'
    )
""")

print("Populando índice (~30s)…")
con.execute("""
    INSERT INTO imoveis_fts(rowid, InscrFisico, NomeResponsavelTributario, EnderecoImovel, CepImovel)
    SELECT rowid, InscrFisico, NomeResponsavelTributario, EnderecoImovel, CepImovel
    FROM imoveis_agregado
""")
con.commit()

print("Otimizando índice…")
con.execute("INSERT INTO imoveis_fts(imoveis_fts) VALUES('optimize')")
con.commit()

sz = con.execute(
    "SELECT page_count * page_size FROM pragma_page_count(), pragma_page_size()"
).fetchone()[0]
con.close()

print(f"\nFTS5 criado em {time.perf_counter()-t:.1f}s  —  banco agora {sz/1e6:.1f} MB")
print("\nPróximo: python etl/05_compress.py")
