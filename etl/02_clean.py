#!/usr/bin/env python3
"""ETL step 2: clean and normalize the imoveis table."""
import sys, os, time, sqlite3, unicodedata
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = Path(__file__).parent.parent / "imoveis_bauru.db"
t0 = time.perf_counter()

sc = sqlite3.connect(str(DB))
sc.execute("PRAGMA journal_mode=WAL")


def count(msg=""):
    n = sc.execute("SELECT COUNT(*) FROM imoveis").fetchone()[0]
    if msg:
        print(f"  {msg}: {n:,} linhas")
    return n


def section(title):
    print(f"\n{'─'*60}")
    print(f"  {title}")
    print(f"{'─'*60}")


def strip_accents(s):
    if s is None:
        return None
    return "".join(
        c for c in unicodedata.normalize("NFD", s)
        if unicodedata.category(c) != "Mn"
    ).upper()


section("ESTADO INICIAL")
total_antes = count("Linhas")
sz_antes = DB.stat().st_size / 1024 / 1024
print(f"  Tamanho inicial: {sz_antes:.1f} MB")
colunas_antes = [r[1] for r in sc.execute("PRAGMA table_info(imoveis)").fetchall()]
print(f"  Colunas ({len(colunas_antes)}): {', '.join(colunas_antes)}")

section("AÇÃO 1 — Recuperar AnoConstrucao dos nulos via DtEdificacao")
antes = sc.execute("SELECT COUNT(*) FROM imoveis WHERE AnoConstrucao IS NULL").fetchone()[0]
sc.execute("""
    UPDATE imoveis
    SET AnoConstrucao = CAST(SUBSTR(DtEdificacao, 1, 4) AS INTEGER)
    WHERE AnoConstrucao IS NULL
      AND DtEdificacao IS NOT NULL
      AND SUBSTR(DtEdificacao, 1, 4) GLOB '[0-9][0-9][0-9][0-9]'
""")
depois = sc.execute("SELECT COUNT(*) FROM imoveis WHERE AnoConstrucao IS NULL").fetchone()[0]
print(f"  Recuperados: {antes - depois:,}  |  ainda nulo: {depois:,}")
sc.commit()

section("AÇÃO 2 — Normalizar ClassificacaoTributaria (remover acentos)")
vals = sc.execute(
    "SELECT DISTINCT ClassificacaoTributaria FROM imoveis WHERE ClassificacaoTributaria IS NOT NULL"
).fetchall()
com_acento = [(v[0], strip_accents(v[0])) for v in vals if v[0] != strip_accents(v[0])]
print(f"  Valores com acento: {len(com_acento)}")
for original, normalizado in com_acento:
    cnt = sc.execute(
        "SELECT COUNT(*) FROM imoveis WHERE ClassificacaoTributaria = ?", (original,)
    ).fetchone()[0]
    print(f"  [{cnt:>6,}]  '{original}' → '{normalizado}'")
    sc.execute(
        "UPDATE imoveis SET ClassificacaoTributaria = ? WHERE ClassificacaoTributaria = ?",
        (normalizado, original),
    )
sc.commit()

section("AÇÃO 3 — Remover colunas desnecessárias")
sc.execute("""
    CREATE TABLE imoveis_clean AS
    SELECT
        InscrFisico, InscrQuadra, NomeResponsavelTributario,
        TipoResponsavelTributario, CPFCNPJRespTrib,
        EnderecoImovel, LogradouroImovel, BairroImovel, CepImovel,
        EnderecoCorresp, AreaTerreno, TotalAreaEdificada,
        Finalidade, TpConstrucao, Categoria, Conservacao,
        AnoConstrucao, ClassificacaoTributaria
    FROM imoveis
""")
sc.execute("DROP TABLE imoveis")
sc.execute("ALTER TABLE imoveis_clean RENAME TO imoveis")
sc.commit()

section("AÇÃO 4 — Recriar índices")
for name, col in [
    ("idx_inscr_fisico",      "InscrFisico"),
    ("idx_bairro_imovel",     "BairroImovel"),
    ("idx_cep_imovel",        "CepImovel"),
    ("idx_logradouro_imovel", "LogradouroImovel"),
    ("idx_nome_resp",         "NomeResponsavelTributario"),
]:
    sc.execute(f'CREATE INDEX "{name}" ON imoveis("{col}")')
    print(f"  {name}")
sc.commit()

section("AÇÃO 5 — VACUUM")
sc.execute("PRAGMA journal_mode=DELETE")
sc.commit()
sc.execute("VACUUM")
sc.close()

sc2 = sqlite3.connect(str(DB))
n_final = sc2.execute("SELECT COUNT(*) FROM imoveis").fetchone()[0]
colunas = [r[1] for r in sc2.execute("PRAGMA table_info(imoveis)").fetchall()]
sc2.close()

sz_depois = DB.stat().st_size / 1024 / 1024
section("RESUMO FINAL")
print(f"  Linhas:    {n_final:>10,}  (antes: {total_antes:,})")
print(f"  Colunas:   {len(colunas):>10}  (antes: {len(colunas_antes)})")
print(f"  Tamanho:   {sz_depois:>9.1f} MB  (antes: {sz_antes:.1f} MB)")
print(f"  Tempo:     {time.perf_counter()-t0:>9.1f} s")
print(f"\nPróximo: python etl/03_aggregate.py")
