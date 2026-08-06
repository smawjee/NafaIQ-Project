import gzip, pickle, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[0]))

from panel import CACHE_PATH  # noqa: E402

with gzip.open(CACHE_PATH, "rb") as fh:
    payload = pickle.load(fh)

print("cache keys:", sorted(payload.keys()))
print("format:", payload.get("format"))
ex = payload["ex_cash"]
print("ex_cash dtype:", ex.dtype, "shape:", ex.shape)
print("non-zero cells:", int((ex != 0).sum()))
print("finite non-zero:", int((ex > 0).sum()))
if (ex > 0).any():
    i, j = (ex > 0).argmax(axis=0), (ex > 0).argmax(axis=1)
    print("sample cell:", payload["dates"][i], payload["symbols"][j], ex[i, j])
