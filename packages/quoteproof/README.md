# quoteproof

Deterministic check that a quote cited by a model is really on the page it cites.
Pure standard library, no I/O, no randomness.

Install: `pip install quoteproof` (build the wheel locally with `uv build --package quoteproof`).

```python
from quoteproof import Citation, Claim, verify_claim

page = {"sha256:abc": "WAL provides more concurrency as readers do not block writers."}
claim = Claim("c1", "WAL helps readers", (Citation("sha256:abc", "concurrency as readers do not block writers"),))
print(verify_claim(claim, page).status)  # verified
```

A claim is `verified` only if every quote is 6 to 80 words and is found in the cited page
after NORM_V1 normalization. Otherwise it is `rejected` with a reason code.
