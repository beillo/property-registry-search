#!/usr/bin/env python3
"""ETL step 5: compress the database for git deployment."""
import gzip, shutil, time
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC  = ROOT / "imoveis_bauru.db"
DST  = ROOT / "imoveis_bauru.db.gz"

print(f"Comprimindo {SRC.name}…")
t = time.perf_counter()
with open(SRC, "rb") as fi, gzip.open(DST, "wb", compresslevel=9) as fo:
    shutil.copyfileobj(fi, fo)

sz_in  = SRC.stat().st_size / 1e6
sz_out = DST.stat().st_size / 1e6
print(f"  {SRC.name}: {sz_in:.1f} MB")
print(f"  {DST.name}: {sz_out:.1f} MB  ({sz_out/sz_in:.0%} do original)")
print(f"  Tempo: {time.perf_counter()-t:.1f}s")
print(f"\nAgora faça commit do {DST.name}.")
