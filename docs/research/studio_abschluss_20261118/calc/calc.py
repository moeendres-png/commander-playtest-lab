import math
import random
from statistics import NormalDist

N = NormalDist()


def z(a):
    return N.inv_cdf(1 - a)


def wilson(k, n, al=0.05):
    zz = z(al / 2)
    p = k / n
    d = 1 + zz * zz / n
    c = (p + zz * zz / (2 * n)) / d
    h = zz * math.sqrt(p * (1 - p) / n + zz * zz / (4 * n * n)) / d
    return c - h, c + h


print("== 1. n for half-width +-3pp, p=0.25 (single focal deck, 1 obs per game)")
for al in (0.05, 0.01):
    zz = z(al / 2)
    d = 0.03
    p = 0.25
    nw = zz * zz * p * (1 - p) / d**2
    # exact: smallest n such that Wilson half-width at k=round(pn) <= d
    n = 100
    while True:
        lo, hi = wilson(round(p * n), n, al)
        if (hi - lo) / 2 <= d:
            break
        n += 1
    print(f" alpha={al}: Wald n={nw:.0f}; Wilson-halfwidth<=3pp at n={n} (k=pn)")
for d in (0.05, 0.02, 0.01):
    zz = z(0.025)
    print(f" +-{d * 100:.0f}pp 95%: n={zz * zz * 0.1875 / d**2:.0f}")
print("== 2. CRN variance factor Var_com/Var_ind = (1-rho) (Owen eq 8.21 with equal sigma)")
for r in (0, 0.1, 0.3, 0.5, 0.7, 0.9):
    print(f" rho={r}: var ratio={1 - r:.2f}, n-saving factor={1 / (1 - r):.2f}x")
print(
    "== 3. Paired (McNemar-type) vs independent n, detect delta=+3pp, p1=.25,p2=.28, alpha .05, power .8"
)
za = z(0.025)
zb = z(0.2)
d = 0.03
p1 = 0.25
p2 = 0.28
n_ind = (za + zb) ** 2 * (p1 * (1 - p1) + p2 * (1 - p2)) / d**2
print(f" independent: n per arm={n_ind:.0f}, total games={2 * n_ind:.0f}")
for t in (0.2, 0.3, 0.4, 0.5):
    n_pair = ((za * math.sqrt(t) + zb * math.sqrt(t - d * d)) / d) ** 2
    print(
        f" paired, discordant fraction t={t}: n pairs={n_pair:.0f}, total games={2 * n_pair:.0f} (x{2 * n_ind / (2 * n_pair):.2f} fewer)"
    )
print("== 4. seat effect: detect seat1 29.1% vs 25% (Playgroup), power .8, one-sample")
p0 = 0.25
p1 = 0.291
n = ((za * math.sqrt(p0 * (1 - p0)) + zb * math.sqrt(p1 * (1 - p1))) / (p1 - p0)) ** 2
print(f" n games ~ {n:.0f}")
print(
    "== 5. Multiplicity: n inflation for same half-width when alpha/m (Bonferroni/Holm worst case)"
)
for m in (1, 10, 50, 100):
    f = (z(0.05 / m / 2) / z(0.025)) ** 2
    print(f" m={m}: z={z(0.05 / m / 2):.2f}, n x{f:.2f}")
print("== 6. Lan-DeMets OBF cumulative alpha spent, 2-sided .05")
for t in (0.2, 0.4, 0.6, 0.8, 1.0):
    print(f" t={t}: {2 * (1 - N.cdf(z(0.025) / math.sqrt(t))):.5f}")
print("== 7. Naive peeking type I error (fair coin p=.25, nominal 5%, looks)")
random.seed(1)


def peek(looks, nfinal=800, reps=4000):
    step = nfinal // looks
    rej = 0
    for _ in range(reps):
        k = 0
        n = 0
        hit = False
        for _L in range(looks):
            k += sum(1 for _ in range(step) if random.random() < 0.25)
            n += step
            ph = k / n
            se = math.sqrt(0.25 * 0.75 / n)
            if abs(ph - 0.25) / se > 1.96:
                hit = True
                break
        rej += hit
    return rej / reps


for L in (1, 2, 5, 10, 20):
    print(f" looks={L}: false-positive ~{peek(L):.3f}")
