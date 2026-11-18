import math, random
random.seed(7)
def gumbel(): return -math.log(-math.log(random.random()))
delta=math.log(3*0.28/0.72)   # focal B: p=.28 vs A: p=.25 against 3 equal opponents (Plackett-Luce = Gumbel-max)
def run(q,N=200000):
    a=b=both=disc=0; n01=n10=0
    for _ in range(N):
        LA=[gumbel() for _ in range(4)]
        LB=LA if random.random()<q else [gumbel() for _ in range(4)]  # q = share of games with shared luck (CRN survives)
        wa = max(range(4),key=lambda i:LA[i]+(0 if i else 0))==0
        sB=[delta,0,0,0]
        wb = max(range(4),key=lambda i:LB[i]+sB[i])==0
        a+=wa;b+=wb
        n10+= wa and not wb; n01+= (not wa) and wb
    pa,pb=a/N,b/N; d=pb-pa
    t=(n10+n01)/N
    var_pair=(t-d*d)/N                    # McNemar-type variance of paired difference
    var_ind=(pa*(1-pa)+pb*(1-pb))/N
    return pa,pb,t,var_ind/var_pair
print("q(share of shared-luck games) | pA | pB | discordant t | variance gain (ind/paired)")
for q in (0,0.5,0.8,0.95,1.0):
    pa,pb,t,g=run(q); print(f"{q:4.2f} | {pa:.4f} | {pb:.4f} | {t:.3f} | {g:.2f}x")
