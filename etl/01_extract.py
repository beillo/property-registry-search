#!/usr/bin/env python3
"""ETL step 1: raw CSV → SQLite via DuckDB."""
import sys, os, time, duckdb, sqlite3
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).parent.parent
CSV  = ROOT / "ExtracaoDadosImoveisGeoPixel.csv"
DB   = ROOT / "imoveis_bauru.db"

t0 = time.perf_counter()

if DB.exists():
    DB.unlink()

SOURCE = (
    "read_csv('" + str(CSV).replace("\\", "/") + "', "
    "delim=';', header=true, encoding='latin-1', "
    "auto_detect=true, ignore_errors=true)"
)

con = duckdb.connect()
print("Carregando CSV...")
con.execute(f"CREATE TABLE raw AS SELECT * FROM {SOURCE}")
print(f"  {con.execute('SELECT COUNT(*) FROM raw').fetchone()[0]:,} linhas brutas")

print("Transformando...")
con.execute("""
CREATE TABLE imoveis AS
SELECT
    InscrFisico,
    InscrQuadra,
    NomeResponsavelTributario,
    TipoResponsavelTributario,
    CPFCNPJRespTrib,

    TRIM(CONCAT_WS(' ',
        TpLogrImovel,
        TituloLogrImovel,
        LogradouroImovel,
        NroImovel,
        ComplImovel
    )) AS EnderecoImovel,

    LogradouroImovel,
    BairroImovel,
    CepImovel,

    TRIM(
        COALESCE(CONCAT_WS(' ',
            TpLogrCorresp,
            TituloLogrCorresp,
            LogradouroCorresp,
            NroCorresp,
            ComplCorresp
        ), '')
        || CASE WHEN BairroCorresp IS NOT NULL
                THEN ', ' || BairroCorresp ELSE '' END
        || CASE WHEN CepCorresp    IS NOT NULL
                THEN ', ' || CepCorresp    ELSE '' END
        || CASE WHEN CidadeCorresp IS NOT NULL
                THEN ', ' || CidadeCorresp ELSE '' END
        || CASE WHEN EstadoCorresp IS NOT NULL
                THEN ' - ' || EstadoCorresp ELSE '' END
    ) AS EnderecoCorresp,

    TRY_CAST(REPLACE(AreaTerreno,           ',', '.') AS DOUBLE) AS AreaTerreno,
    TRY_CAST(REPLACE(AreaTerrenoTributavel,  ',', '.') AS DOUBLE) AS AreaTerrenoTributavel,
    TRY_CAST(REPLACE(TotalAreaEdificada,     ',', '.') AS DOUBLE) AS TotalAreaEdificada,
    TRY_CAST(REPLACE(Area,                   ',', '.') AS DOUBLE) AS Area,

    Finalidade,
    DtEdificacao,
    TpConstrucao,
    Categoria,
    Conservacao,
    AnoConstrucao,
    ClassificacaoTributaria

FROM raw
""")

total = con.execute("SELECT COUNT(*) FROM imoveis").fetchone()[0]
print(f"  {total:,} linhas, {con.execute('DESCRIBE imoveis').fetchdf().shape[0]} colunas")

print("Exportando para SQLite...")
df = con.execute("SELECT * FROM imoveis").fetchdf()
con.close()

sc = sqlite3.connect(str(DB))
df.to_sql("imoveis", sc, if_exists="replace", index=False)
del df

print("Criando índices...")
indexes = [
    ("idx_inscr_fisico",      "InscrFisico"),
    ("idx_bairro_imovel",     "BairroImovel"),
    ("idx_cep_imovel",        "CepImovel"),
    ("idx_logradouro_imovel", "LogradouroImovel"),
    ("idx_nome_resp",         "NomeResponsavelTributario"),
]
for name, col in indexes:
    sc.execute(f'CREATE INDEX "{name}" ON imoveis("{col}")')

sc.commit()
sc.close()

elapsed = time.perf_counter() - t0
db_size = DB.stat().st_size
print(f"\n{'='*52}")
print(f"  Linhas gravadas :  {total:>12,}")
print(f"  Tamanho .db     :  {db_size/1024/1024:>11.1f} MB")
print(f"  Tempo total     :  {elapsed:>11.1f} s")
print(f"{'='*52}")
print(f"\nPróximo: python etl/02_clean.py")
