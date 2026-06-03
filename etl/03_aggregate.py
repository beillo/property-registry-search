#!/usr/bin/env python3
"""ETL step 3: deduplicate and aggregate records by property ID."""
import sys, os, time, sqlite3
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DB = Path(__file__).parent.parent / "imoveis_bauru.db"
t0 = time.perf_counter()

sc = sqlite3.connect(str(DB))
sc.execute("PRAGMA journal_mode=WAL")
sc.execute("PRAGMA synchronous=NORMAL")


def lap(msg):
    print(f"  {msg:55s} {time.perf_counter()-t0:>5.1f}s")


def section(t):
    print(f"\n{'─'*62}\n  {t}\n{'─'*62}")


section("AÇÃO 1 — Atualizar EnderecoImovel (+ bairro + CEP)")
sc.execute("""
    UPDATE imoveis
    SET EnderecoImovel =
        TRIM(
            COALESCE(EnderecoImovel, '')
            || CASE WHEN BairroImovel IS NOT NULL AND BairroImovel != ''
                    THEN ', ' || BairroImovel ELSE '' END
            || CASE WHEN CepImovel IS NOT NULL AND CepImovel != ''
                    THEN ' - ' || CepImovel ELSE '' END
        )
""")
sc.commit()
lap("EnderecoImovel atualizado")

section("AÇÃO 2 — Remover InscrQuadra e LogradouroImovel")
sc.execute("""
    CREATE TABLE imoveis_v2 AS
    SELECT
        InscrFisico, NomeResponsavelTributario, TipoResponsavelTributario,
        CPFCNPJRespTrib, EnderecoImovel, BairroImovel, CepImovel,
        EnderecoCorresp, AreaTerreno, TotalAreaEdificada,
        Finalidade, TpConstrucao, Categoria, Conservacao,
        AnoConstrucao, ClassificacaoTributaria
    FROM imoveis
""")
sc.execute("DROP TABLE imoveis")
sc.execute("ALTER TABLE imoveis_v2 RENAME TO imoveis")
sc.commit()
for name, col in [
    ("idx_inscr_fisico",  "InscrFisico"),
    ("idx_bairro_imovel", "BairroImovel"),
    ("idx_cep_imovel",    "CepImovel"),
    ("idx_nome_resp",     "NomeResponsavelTributario"),
]:
    sc.execute(f'CREATE INDEX "{name}" ON imoveis("{col}")')
sc.commit()
lap("Tabela imoveis recriada (16 colunas), índices recriados")

section("AÇÃO 3 — Agregar por InscrFisico → imoveis_agregado")
sc.execute("DROP TABLE IF EXISTS imoveis_agregado")
sc.execute("""
    CREATE TABLE imoveis_agregado AS
    SELECT
        InscrFisico,
        MIN(NomeResponsavelTributario)   AS NomeResponsavelTributario,
        MIN(TipoResponsavelTributario)   AS TipoResponsavelTributario,
        MIN(CPFCNPJRespTrib)             AS CPFCNPJRespTrib,
        MIN(EnderecoImovel)              AS EnderecoImovel,
        MIN(BairroImovel)               AS BairroImovel,
        MIN(CepImovel)                  AS CepImovel,
        MIN(EnderecoCorresp)             AS EnderecoCorresp,
        MAX(AreaTerreno)                 AS AreaTerreno,
        MAX(TotalAreaEdificada)          AS TotalAreaEdificada,
        MIN(ClassificacaoTributaria)     AS ClassificacaoTributaria,
        REPLACE(GROUP_CONCAT(DISTINCT Finalidade),   ',', ' | ')  AS Finalidade,
        REPLACE(GROUP_CONCAT(DISTINCT TpConstrucao), ',', ' | ')  AS TpConstrucao,
        REPLACE(GROUP_CONCAT(DISTINCT Categoria),    ',', ' | ')  AS Categoria,
        REPLACE(GROUP_CONCAT(DISTINCT Conservacao),  ',', ' | ')  AS Conservacao,
        MIN(AnoConstrucao)              AS AnoConstrucao
    FROM imoveis
    GROUP BY InscrFisico
""")
sc.commit()
lap("imoveis_agregado criada")

n_agr  = sc.execute("SELECT COUNT(*) FROM imoveis_agregado").fetchone()[0]
n_orig = sc.execute("SELECT COUNT(*) FROM imoveis").fetchone()[0]
print(f"  {n_orig:,} linhas → {n_agr:,} imóveis únicos")

section("AÇÃO 4 — Índices em imoveis_agregado")
for name, col in [
    ("idx_agg_inscr",  "InscrFisico"),
    ("idx_agg_bairro", "BairroImovel"),
    ("idx_agg_cep",    "CepImovel"),
    ("idx_agg_nome",   "NomeResponsavelTributario"),
]:
    sc.execute(f'CREATE INDEX "{name}" ON imoveis_agregado("{col}")')
    print(f"  {name}")
sc.commit()

section("AÇÃO 5 — VACUUM")
sc.execute("PRAGMA journal_mode=DELETE")
sc.commit()
sc.execute("VACUUM")
sc.close()
lap("VACUUM concluído")

sz = DB.stat().st_size / 1024 / 1024
section("RESUMO FINAL")
print(f"  imoveis         : {n_orig:,} linhas")
print(f"  imoveis_agregado: {n_agr:,} linhas")
print(f"  Tamanho .db     : {sz:.1f} MB")
print(f"  Tempo total     : {time.perf_counter()-t0:.1f} s")
print(f"\nPróximo: python etl/04_setup_fts.py")
