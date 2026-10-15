#!/usr/bin/env python3
"""Assemble per-release RNG evidence into a game catalog and manifest."""
from __future__ import annotations
import argparse,hashlib,json
from pathlib import Path

def file_hash(path:Path):return hashlib.sha256(path.read_bytes()).hexdigest()
def build(root:Path,catalog_path:Path,prefix:str,game:str):
 catalog=json.loads((root/catalog_path).read_text(encoding='utf-8'));origin_map=Path(f'analysis/{prefix}-jp-rng-map.json');origin=json.loads((root/origin_map).read_text(encoding='utf-8'));origin_hash=origin['target']['sha256'];records=[];outputs=[Path('src/random.c'),catalog_path]
 for rel in catalog['releases']:
  if rel['sha256']==origin_hash:
   paths={'map':origin_map,'random_cfg':Path(f'analysis/{prefix}-jp-random-cfg.json'),'seed_cfg':Path(f'analysis/{prefix}-jp-seed-rng-cfg.json')};is_origin=True
  else:
   rid=rel['id'];paths={'map':Path(f'analysis/{rid}-rng-map.json'),'random_cfg':Path(f'analysis/{rid}-random-cfg.json'),'seed_cfg':Path(f'analysis/{rid}-seed-rng-cfg.json')};is_origin=False
  m=json.loads((root/paths['map']).read_text(encoding='utf-8'))
  if m['target']['sha256']!=rel['sha256']:raise ValueError(f"evidence hash mismatch: {rel['id']}")
  records.append({'id':rel['id'],'language':rel['language'],'revision':rel['revision'],'build_kind':rel['build_kind'],'sha256':rel['sha256'],'origin_reference':is_origin,'evidence':{k:v.as_posix() for k,v in paths.items()},'functions':m['functions'],'globals':m['globals']});outputs.extend(paths.values())
 summary={'schema_version':1,'game':game,'origin_reference':'Japanese','release_count':len(records),'releases':records,'algorithm':{'state_bits':32,'multiplier':1103515245,'increment':24691,'return_bits':'state[31:16]'},'raw_rom_bytes_included':False};summary_path=Path('analysis/rng-catalog-summary.json');(root/summary_path).write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n');outputs.append(summary_path)
 outputs += [Path('research/rng-catalog-reconstruction.md'),Path('tests/test_rng_catalog_reconstruction.py')];missing=[p.as_posix()for p in outputs if not(root/p).is_file()]
 if missing:raise ValueError('missing output(s): '+', '.join(missing))
 manifest={'schema_version':1,'game':game,'release_count':len(records),'generator':{'repository':'SakuraiTsubaki/Decompilation','tool':'tools/build_rng_catalog_evidence.py','tool_sha256':file_hash(Path(__file__))},'outputs':[{'path':p.as_posix(),'sha256':file_hash(root/p)}for p in outputs],'raw_rom_bytes_included':False};(root/'manifests/rng-catalog-reconstruction.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
 return summary,manifest
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--catalog',type=Path,default=Path('analysis/global-release-catalog.json'));p.add_argument('--prefix',required=True);p.add_argument('--game',required=True);a=p.parse_args()
 try:build(a.root,a.catalog,a.prefix,a.game)
 except(OSError,KeyError,ValueError,json.JSONDecodeError)as e:p.error(str(e))
 return 0
if __name__=='__main__':raise SystemExit(main())
