import re, sys, pathlib
src = pathlib.Path(sys.argv[1]).read_text()
out = pathlib.Path(sys.argv[2]); out.mkdir(exist_ok=True)
files = re.split(r'(?m)^(?=diff --git )', src)
labels = {
 ('AbilitiesImpl.java',0):'singleton_def',
 ('TriggeredAbilities.java',0):'trig',
 ('CardImpl.java',0):'p2',
 ('GameState.java',0):'p1',
 ('PlayerImpl.java',0):'nested_mana',
 ('PlayerImpl.java',1):'singleton_use1',
 ('PlayerImpl.java',2):'singleton_use2',
 ('PlayerImpl.java',3):'nested_playable',
}
for f in files:
    if not f.strip(): continue
    m = re.match(r'diff --git a/(\S+)', f); path = m.group(1); name = path.split('/')[-1]
    head, *hunks = re.split(r'(?m)^(?=@@ )', f)
    for i,h in enumerate(hunks):
        lab = labels[(name,i)]
        (out/f'{lab}.patch').write_text(head + h)
        print(lab, path, h.splitlines()[0])
