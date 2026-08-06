from __future__ import annotations
import json, math, shutil
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean
from typing import Any
from commander_lab.models.local_meta import *
from commander_lab.storage.hashing import sha256_value

class LocalMetaConflictError(RuntimeError): pass

def _wilson(count:int,total:int,z:float=1.96)->tuple[float,float]:
    if total<=0:return (0.0,1.0)
    p=count/total; den=1+z*z/total; center=(p+z*z/(2*total))/den
    margin=z*math.sqrt((p*(1-p)+z*z/(4*total))/total)/den
    return (max(0,center-margin),min(1,center+margin))

def _estimate(count:int,total:int,prior_mean:float,prior_strength:float=8.0)->LocalFrequencyEstimate:
    raw=count/total if total else 0.0
    shrunk=(count+prior_mean*prior_strength)/(total+prior_strength)
    lo,hi=_wilson(count,total) if total else (0.0,1.0)
    return LocalFrequencyEstimate(observations=total,count=count,raw_frequency=raw,shrunk_frequency=shrunk,uncertainty_interval=(lo,hi),prior_strength=prior_strength)

class LocalMetaStore:
    def __init__(self,root:str|Path)->None:
        self.root=Path(root).resolve(); self.base=self.root/'data/local_meta'; self.games=self.base/'games'; self.profiles=self.base/'profiles'
        self.games.mkdir(parents=True,exist_ok=True); self.profiles.mkdir(parents=True,exist_ok=True); (self.base/'backups').mkdir(parents=True,exist_ok=True); (self.base/'exports').mkdir(parents=True,exist_ok=True)
    @staticmethod
    def game_hash(game:LocalGameRecord)->str:
        return sha256_value(game.model_dump(mode='json',exclude={'ingested_at','raw_hash'}))
    def ingest(self,game:LocalGameRecord)->dict[str,Any]:
        target=self.games/f'{game.game_id}.json'; payload=game.model_dump(mode='json',exclude={'ingested_at','raw_hash'}); h=sha256_value(payload)
        if game.correction_of:
            original=self.games/f'{game.correction_of}.json'
            if not original.exists(): raise LocalMetaConflictError('correction references unknown game')
            if game.game_id==game.correction_of: raise LocalMetaConflictError('correction must use a new game_id')
        if target.exists():
            existing=LocalGameRecord.model_validate_json(target.read_text())
            if self.game_hash(existing)!=h: raise LocalMetaConflictError('game ID already exists with different content')
            return {'game_id':game.game_id,'game_hash':h,'duplicate_identical':True,'appended':False}
        final=game.model_copy(update={'raw_hash':h})
        target.write_text(json.dumps(final.model_dump(mode='json'),indent=2,sort_keys=True)+'\n')
        backup=self.base/'backups'/f'{game.game_id}-{h[:12]}.json'; shutil.copy2(target,backup)
        return {'game_id':game.game_id,'game_hash':h,'duplicate_identical':False,'appended':True,'backup_path':str(backup.relative_to(self.root))}
    def load_games(self)->list[LocalGameRecord]:
        return [LocalGameRecord.model_validate_json(p.read_text()) for p in sorted(self.games.glob('*.json'))]
    def split(self,games:list[LocalGameRecord])->tuple[tuple[str,...],tuple[str,...]]:
        train=[]; val=[]
        for g in games:
            (val if int(sha256_value(g.game_id)[:8],16)%5==0 else train).append(g.game_id)
        return tuple(sorted(train)),tuple(sorted(val))
    def update_profile(self,opponent_key:str,commander:str,deck_version_label:str='unknown')->LocalOpponentProfileVersion:
        games=self.load_games(); relevant=[]
        for game in games:
            for p in game.participants:
                if p.public_label==opponent_key or p.commander==commander: relevant.append((game,p))
        versions=[]
        for path in self.profiles.glob(f'{opponent_key}_observed_v*.json'):
            try: versions.append(LocalOpponentProfileVersion.model_validate_json(path.read_text()))
            except Exception: pass
        version=max([x.version for x in versions],default=0)+1
        card_map:dict[tuple[str,ObservationStatus],int]=Counter(); role_map:dict[str,int]=Counter(); turns=[]; rem=0; wipes=0; commander_cast_games=0; win_axes=set(); dates=[]
        for game,p in relevant:
            if game.turns is not None: turns.append(game.turns)
            if game.played_on: dates.append(game.played_on)
            rem+=p.removal_used or 0; wipes+=p.boardwipes_used or 0
            commander_cast_games+=int((p.commander_casts or 0)>0)
            if p.win_axis: win_axes.add(p.win_axis)
            for c in p.visible_cards: card_map[(c.card_name,c.status)]+=c.occurrences
            for r in p.engines_seen: role_map[r]+=1
        total=len(relevant)
        cards=tuple(LocalCardObservation(card_name=n,status=s,occurrences=c) for (n,s),c in sorted(card_map.items(),key=lambda x:(x[0][0],x[0][1])))
        roles=tuple(LocalRoleObservation(role=r,status=ObservationStatus.INFERRED_ROLE,confidence=min(.85,.35+c/max(1,total)*.5)) for r,c in sorted(role_map.items()))
        speed=NumericRange(minimum=min(turns),maximum=max(turns)) if turns else None
        pid=f'{opponent_key}_observed_v{version}'
        provisional={'profile_id':pid,'opponent_key':opponent_key,'version':version,'commander':commander,'deck_version_label':deck_version_label,'based_on_game_ids':tuple(sorted({g.game_id for g,_ in relevant})),'observed_cards':cards,'observed_roles':roles,'possible_roles':(), 'speed_turn_range':speed,'interaction_density':_estimate(rem,total,0.20),'wipe_density':_estimate(wipes,total,0.08),'commander_dependency':_estimate(commander_cast_games,total,0.5),'win_axes':tuple(sorted(win_axes)),'uncertainty_notes':(('No real games imported; profile remains an empty observation shell.',) if total==0 else ('Small samples are shrunk toward the starting profile.',)),'sample_size':total,'data_quality':'insufficient_data' if total<5 else 'provisional_observed','last_observed_at':max(dates) if dates else None,'profile_hash':'0'*64,'supersedes_profile_id':versions[-1].profile_id if versions else None,'official_precon_superseded':False}
        provisional['profile_hash']=sha256_value({k:v for k,v in provisional.items() if k!='profile_hash'})
        profile=LocalOpponentProfileVersion.model_validate(provisional)
        (self.profiles/f'{pid}.json').write_text(json.dumps(profile.model_dump(mode='json'),indent=2,sort_keys=True)+'\n')
        return profile
    def profiles_latest(self)->list[LocalOpponentProfileVersion]:
        allp=[LocalOpponentProfileVersion.model_validate_json(p.read_text()) for p in self.profiles.glob('*.json')]
        latest={}
        for p in allp:
            if p.opponent_key not in latest or p.version>latest[p.opponent_key].version: latest[p.opponent_key]=p
        return [latest[k] for k in sorted(latest)]
    def inspect(self)->dict[str,Any]:
        games=self.load_games(); profiles=self.profiles_latest(); train,val=self.split(games)
        dates=[g.played_on for g in games if g.played_on]
        return {'real_game_count':len(games),'profile_count':len(profiles),'profiles':[p.model_dump(mode='json') for p in profiles],'train_game_ids':train,'validation_game_ids':val,'last_observation':max(dates).isoformat() if dates else None,'data_quality':'insufficient_data' if len(games)<5 else 'provisional_observed','fixed_opponent_percentages':False}
    def compare_observed_to_assumed(self,opponent_key:str,assumed_profile:dict[str,Any]|None=None)->dict[str,Any]:
        profile=next((p for p in self.profiles_latest() if p.opponent_key==opponent_key),None)
        if not profile: raise KeyError(opponent_key)
        assumed_profile=assumed_profile or {}
        return {'profile_id':profile.profile_id,'sample_size':profile.sample_size,'observed_cards':[x.card_name for x in profile.observed_cards],'assumed_roles':assumed_profile.get('roles',[]),'observed_roles':[x.role for x in profile.observed_roles],'complete_deck_inferred':False,'official_precon_overwritten':False}
    def detect_drift(self,opponent_key:str)->dict[str,Any]:
        versions=sorted([LocalOpponentProfileVersion.model_validate_json(p.read_text()) for p in self.profiles.glob(f'{opponent_key}_observed_v*.json')],key=lambda x:x.version)
        if len(versions)<2:return {'opponent_key':opponent_key,'drift_status':'insufficient_versions','versions':len(versions)}
        a,b=versions[-2:]; old={x.card_name for x in a.observed_cards}; new={x.card_name for x in b.observed_cards}
        return {'opponent_key':opponent_key,'older':a.profile_id,'newer':b.profile_id,'new_cards':sorted(new-old),'missing_previous_cards':sorted(old-new),'speed_changed':a.speed_turn_range!=b.speed_turn_range,'small_sample':min(a.sample_size,b.sample_size)<5}
    def build_scenarios(self)->dict[str,Any]:
        rows=[]
        for p in self.profiles_latest():
            rows.append({'scenario_id':f'local-{p.profile_id}','profile_id':p.profile_id,'usage_modes':['primary_scenario','holdout','sensitivity_variant','opponent_ensemble'],'known_cards':[x.card_name for x in p.observed_cards if x.status==ObservationStatus.DIRECTLY_OBSERVED],'possible_roles':[x.role for x in p.possible_roles],'synthetic_completion':False,'official_precon_overwritten':False,'uncertainty_notes':p.uncertainty_notes})
        return {'scenarios':rows,'real_game_count':len(self.load_games()),'estimate_type':'empirical_playtest_observations' if self.load_games() else 'insufficient_real_data'}
