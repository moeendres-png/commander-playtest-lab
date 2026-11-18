import math
from statistics import NormalDist
N=NormalDist(); za=N.inv_cdf(.975); zb=N.inv_cdf(.8)
def mde_ind(n,p=.25):
    lo,hi=1e-4,.5
    for _ in range(80):
        d=(lo+hi)/2
        need=(za+zb)**2*(p*(1-p)+(p+d)*(1-p-d))/d**2
        lo,hi=(d,hi) if need>n else (lo,d)
    return d
def mde_pair(n,t):
    lo,hi=1e-4,math.sqrt(t)-1e-6
    for _ in range(80):
        d=(lo+hi)/2
        need=((za*math.sqrt(t)+zb*math.sqrt(t-d*d))/d)**2
        lo,hi=(d,hi) if need>n else (lo,d)
    return d
print("MDE (95% two-sided, power 80%), baseline p=.25")
for n in (500,1000,2000,5000):
    print(f"n={n}/arm independent: {mde_ind(n)*100:.1f} pp | paired n pairs={n}: "+", ".join(f"t={t}: {mde_pair(n,t)*100:.1f}pp" for t in (0.39,0.3,0.2,0.1)))
# corrected sample-size table at delta=.03
d=.03;p1=.25;p2=.28
n_ind=(za+zb)**2*(p1*(1-p1)+p2*(1-p2))/d**2
print("t_indep=",p1*(1-p2)+p2*(1-p1))
for t in (0.39,0.3,0.2,0.1):
    npair=((za*math.sqrt(t)+zb*math.sqrt(t-d*d))/d)**2
    print(f"t={t}: pairs={npair:.0f} (games {2*npair:.0f}) vs ind games {2*n_ind:.0f}")
