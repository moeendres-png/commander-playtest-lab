from pathlib import Path
import os,json,subprocess,shutil,yaml
repo=Path('/home/moeen/work/ci479-lab-b11-20261004')
out=Path('/home/moeen/work/takeover-evidence-20261003/B11-live-scopes')
assert not out.exists()
shutil.move(repo/'artifacts/security',out)
workflow=yaml.safe_load((repo/'.github/workflows/ci.yml').read_text())
steps=workflow['jobs']['security']['steps']
env=os.environ.copy(); env['PATH']='/home/moeen/work/b11-clean-tools-20261004/bin:/usr/bin:/bin'
results={'prepare-scopes':{'outcome':'success'}}
commands={}
for step in steps:
 key=step.get('id')
 if key not in ('audit-tooling','audit-product','sbom-tooling','sbom-product','licenses-tooling','licenses-product'): continue
 script=step['run'].replace('artifacts/security',str(out)).replace('$RUNNER_TEMP/security-product-venv','/home/moeen/work/b11-product-20261004')
 commands[key]=script
 p=subprocess.run(['bash','-e','-o','pipefail','-c',script],cwd=repo,env=env,capture_output=True,text=True,timeout=600)
 results[key]={'outcome':'success' if p.returncode==0 else 'failure'}
 (out/(key+'.local.log')).write_text(p.stdout+p.stderr)
 print(json.dumps({'step':key,'exit':p.returncode,'tail':(p.stdout+p.stderr)[-400:]}),flush=True)
env['B11_STEP_RESULTS']=json.dumps(results)
command=['/home/moeen/work/b11-clean-tools-20261004/bin/python','scripts/security_evidence.py','seal','--repo',str(repo),'--wheel-dir',str(repo/'dist'),'--runtime','/home/moeen/work/b11-product-20261004','--out',str(out)]
p=subprocess.run(command,cwd=repo,env=env,capture_output=True,text=True,timeout=120)
print(json.dumps({'seal_exit':p.returncode,'out':p.stdout,'err':p.stderr}),flush=True)
(out/'LOCAL_EXECUTION.json').write_text(json.dumps({'commands':commands,'actual_outcomes':results,'seal_command':command,'seal_exit':p.returncode,'python':'3.14.4','hosted_python312':'NOT_RUN'},indent=2)+'\n')
raise SystemExit(p.returncode)
