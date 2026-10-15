#!/usr/bin/env python3
"""Locate Gen III RNG functions and build multilingual reconstruction evidence."""
from __future__ import annotations
import argparse,csv,hashlib,json,struct,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import rng_evidence

def locate_pattern(data:bytes,pattern:tuple[int,...])->int:
    needle=struct.pack(f'<{len(pattern)}H',*pattern);found=[];start=0
    while True:
      offset=data.find(needle,start)
      if offset<0:break
      if offset%2==0:found.append(offset)
      start=offset+1
    if len(found)!=1:raise ValueError(f'expected one instruction pattern, found {len(found)}')
    return found[0]

def analyze(data:bytes,variant:str):
    random_offset=locate_pattern(data,rng_evidence.RANDOM_PATTERNS[variant])
    seed_offset=locate_pattern(data,rng_evidence.SEED_PATTERNS[variant])
    result=rng_evidence.analyze(data,random_offset,seed_offset,variant)
    result['located_offsets']={'Random':random_offset,'SeedRng':seed_offset}
    return result

def build_manifest(root:Path):
    outputs=[Path('src/random.c'),Path('analysis/emerald-jp-rng-map.json'),Path('analysis/emerald-jp-random-cfg.json'),Path('analysis/emerald-jp-seed-rng-cfg.json')]
    for lang in ('en','de','fr','it','es'):
      outputs += [Path(f'analysis/emerald-{lang}-rng-map.json'),Path(f'analysis/emerald-{lang}-random-cfg.json'),Path(f'analysis/emerald-{lang}-seed-rng-cfg.json')]
    outputs += [Path('analysis/global-release-catalog.json'),Path('research/rng-global-reconstruction.md'),Path('tests/test_rng_global_reconstruction.py')]
    missing=[p.as_posix() for p in outputs if not(root/p).is_file()]
    if missing:raise ValueError('missing manifest output(s): '+', '.join(missing))
    manifest={'schema_version':1,'game':'Pokemon Emerald','origin_reference':'Japanese','official_languages':['Japanese','English','German','French','Italian','Spanish'],'functions':['Random','SeedRng'],'generator':{'repository':'SakuraiTsubaki/Decompilation','tool':'tools/rng_matrix_evidence.py','tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'outputs':[{'path':p.as_posix(),'sha256':hashlib.sha256((root/p).read_bytes()).hexdigest()}for p in outputs],'raw_rom_bytes_included':False}
    (root/'manifests/rng-global-reconstruction.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('rom',type=Path);p.add_argument('--variant',choices=tuple(rng_evidence.RANDOM_PATTERNS),required=True);p.add_argument('--expected-sha256',required=True);p.add_argument('--release',required=True);p.add_argument('--reference-repository',required=True);p.add_argument('--reference-commit',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--root',type=Path);a=p.parse_args();data=a.rom.read_bytes();digest=hashlib.sha256(data).hexdigest()
 if digest!=a.expected_sha256.lower():p.error('ROM SHA-256 mismatch')
 try:r=analyze(data,a.variant)
 except(ValueError,struct.error)as e:p.error(str(e))
 r['target']={'release':a.release,'sha256':digest};r['naming_basis']={'repository':a.reference_repository,'commit':a.reference_commit,'path':'src/random.c','raw_rom_bytes_published':False};a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
 if a.root:
  try:build_manifest(a.root)
  except(OSError,ValueError)as e:p.error(str(e))
 return 0
if __name__=='__main__':raise SystemExit(main())
