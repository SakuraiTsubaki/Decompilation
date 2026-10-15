#!/usr/bin/env python3
"""Locate and verify Emerald's independent secondary RNG stream."""
from __future__ import annotations
import argparse,hashlib,json,struct
from pathlib import Path

ROM_BASE=0x08000000;MULTIPLIER=1103515245;INCREMENT=24691
SEED_PATTERN=(0x0400,0x0C00,0x4901,0x6008,0x4770)
RANDOM_PATTERN=(0x4A04,0x6811,0x4804,0x4348,0x4904,0x1840,0x6010,0x0C00,0x4770)

def locate_all(data,pattern):
 n=struct.pack(f'<{len(pattern)}H',*pattern);hits=[];s=0
 while True:
  o=data.find(n,s)
  if o<0:break
  if o%2==0:hits.append(o)
  s=o+1
 return hits
def locate(data,pattern):
 hits=locate_all(data,pattern)
 if len(hits)!=1:raise ValueError(f'expected one secondary RNG pattern, found {len(hits)}')
 return hits[0]
def record(data,o,n):return {'address':f'0x{ROM_BASE+o:08X}','range_end_exclusive':f'0x{ROM_BASE+o+n:08X}','rom_code_range':{'start_offset':o,'end_offset_exclusive':o+n,'length':n,'sha256':hashlib.sha256(data[o:o+n]).hexdigest(),'raw_bytes_published':False}}
def analyze(data):
 random_bytes=struct.pack(f'<{len(RANDOM_PATTERN)}H',*RANDOM_PATTERN);pairs=[]
 for seed in locate_all(data,SEED_PATTERN):
  random=seed+16
  if data[random:random+len(random_bytes)]==random_bytes and struct.unpack_from('<I',data,seed+12)[0]==struct.unpack_from('<I',data,random+20)[0]:pairs.append((seed,random))
 if len(pairs)!=1:raise ValueError(f'expected one adjacent SeedRng2/Random2 pair, found {len(pairs)}')
 s,r=pairs[0]
 seed_state=struct.unpack_from('<I',data,s+12)[0];random_state=struct.unpack_from('<I',data,r+20)[0]
 if seed_state!=random_state:raise ValueError('SeedRng2 and Random2 state addresses differ')
 if struct.unpack_from('<I',data,r+24)[0]!=MULTIPLIER or struct.unpack_from('<I',data,r+28)[0]!=INCREMENT:raise ValueError('secondary LCG constants differ')
 return {'schema_version':1,'algorithm':{'state_bits':32,'multiplier':MULTIPLIER,'increment':INCREMENT,'return_bits':'state[31:16]','independent_from_primary':True},'globals':{'gRng2Value':f'0x{seed_state:08X}'},'functions':{'SeedRng2':record(data,s,len(SEED_PATTERN)*2),'Random2':record(data,r,len(RANDOM_PATTERN)*2)},'located_offsets':{'SeedRng2':s,'Random2':r},'raw_rom_bytes_included':False}
def manifest(root):
 out=[Path('src/random.c')]
 for l in ('jp','en','de','fr','it','es'):out += [Path(f'analysis/emerald-{l}-rng2-map.json'),Path(f'analysis/emerald-{l}-seed-rng2-cfg.json'),Path(f'analysis/emerald-{l}-random2-cfg.json')]
 out += [Path('analysis/global-release-catalog.json'),Path('research/rng2-global-reconstruction.md'),Path('tests/test_rng2_global_reconstruction.py')];missing=[p.as_posix()for p in out if not(root/p).is_file()]
 if missing:raise ValueError('missing manifest output(s): '+', '.join(missing))
 m={'schema_version':1,'game':'Pokemon Emerald','origin_reference':'Japanese','official_languages':['Japanese','English','German','French','Italian','Spanish'],'functions':['SeedRng2','Random2'],'generator':{'repository':'SakuraiTsubaki/Decompilation','tool':'tools/rng2_evidence.py','tool_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},'outputs':[{'path':p.as_posix(),'sha256':hashlib.sha256((root/p).read_bytes()).hexdigest()}for p in out],'raw_rom_bytes_included':False};(root/'manifests/rng2-global-reconstruction.json').write_text(json.dumps(m,indent=2)+'\n',encoding='utf-8',newline='\n')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('rom',type=Path);p.add_argument('--expected-sha256',required=True);p.add_argument('--release',required=True);p.add_argument('--reference-commit',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--root',type=Path);a=p.parse_args();d=a.rom.read_bytes();h=hashlib.sha256(d).hexdigest()
 if h!=a.expected_sha256.lower():p.error('ROM SHA-256 mismatch')
 try:r=analyze(d)
 except(ValueError,struct.error)as e:p.error(str(e))
 r['target']={'release':a.release,'sha256':h};r['naming_basis']={'repository':'pret/pokeemerald','commit':a.reference_commit,'path':'src/random.c','raw_rom_bytes_published':False};a.output.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n')
 if a.root:
  try:manifest(a.root)
  except(OSError,ValueError)as e:p.error(str(e))
 return 0
if __name__=='__main__':raise SystemExit(main())
