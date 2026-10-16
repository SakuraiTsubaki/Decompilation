#!/usr/bin/env python3
"""Extend a Japanese Gen III trainer-ID reconstruction across a release catalog."""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
import thumb_cfg

SLUGS={'write_word_to_mem':'write-word','copy_word_to_mem':'copy-word','SetTrainerId':'set-trainer-id','GetTrainerId':'get-trainer-id','CopyTrainerId':'copy-trainer-id'}
def digest(data):return hashlib.sha256(data).hexdigest()
def file_hash(path):return digest(path.read_bytes())
def write_json(path,value):path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
def unique_offset(data,signature):
 found=[];start=0
 while True:
  offset=data.find(signature,start)
  if offset<0:break
  if offset%2==0:found.append(offset)
  start=offset+1
 if len(found)!=1:raise ValueError(f'expected one aligned function signature, found {len(found)}')
 return found[0]
def rom_index(directory):
 result={}
 for path in directory.iterdir():
  if path.is_file() and path.suffix.lower()=='.gba':result.setdefault(file_hash(path),path)
 return result
def build(root,rom_dir,catalog_path,origin_map_path,game):
 catalog=json.loads((root/catalog_path).read_text(encoding='utf-8'));origin=json.loads((root/origin_map_path).read_text(encoding='utf-8'));roms=rom_index(rom_dir);origin_sha=origin['target']['sha256']
 if origin_sha not in roms:raise ValueError('origin ROM is missing')
 origin_data=roms[origin_sha].read_bytes();signatures=[]
 for record in origin['functions']:
  r=record['rom_code_range'];signature=origin_data[r['start_offset']:r['end_offset_exclusive']]
  if digest(signature)!=r['sha256']:raise ValueError(f"origin range hash mismatch: {record['name']}")
  signatures.append((record['name'],signature))
 outputs=[Path('src/trainer_id.c'),catalog_path];releases=[]
 for rel in catalog['releases']:
  sha=rel['sha256'];rid=rel['id']
  if sha not in roms:raise ValueError(f'missing catalog ROM: {rid}')
  if sha==origin_sha:
   map_path=origin_map_path;mapping=origin;cfg_paths=[Path(x['cfg']) for x in mapping['functions']];is_origin=True
  else:
   data=roms[sha].read_bytes();records=[];cfg_paths=[];prior_end=None
   for name,signature in signatures:
    offset=unique_offset(data,signature)
    if prior_end is not None and offset!=prior_end:raise ValueError(f'non-adjacent helper sequence: {rid}')
    cfg=thumb_cfg.omit_raw_halfwords(thumb_cfg.trace_thumb_function(data,offset,max_span=len(signature)))
    cfg.update({'source_size':len(data),'source_sha256':sha})
    if cfg['range_end']!=0x08000000+offset+len(signature) or len(cfg['returns'])!=1 or cfg['calls']:raise ValueError(f'CFG boundary mismatch: {rid}/{name}')
    cfg_path=Path(f'analysis/{rid}-{SLUGS[name]}-cfg.json');write_json(root/cfg_path,cfg);cfg_paths.append(cfg_path);prior_end=offset+len(signature)
    records.append({'name':name,'address':f'0x{0x08000000+offset:08X}','range_end_exclusive':f'0x{0x08000000+offset+len(signature):08X}','rom_code_range':{'start_offset':offset,'end_offset_exclusive':offset+len(signature),'length':len(signature),'sha256':digest(signature),'raw_bytes_published':False},'cfg':cfg_path.as_posix(),'edge_count':len(cfg['edges']),'return_count':len(cfg['returns'])})
   mapping={'schema_version':1,'target':{'release':rid,'sha256':sha},'variant':origin['variant'],'source':'src/trainer_id.c','source_sha256':file_hash(root/'src/trainer_id.c'),'byte_order':'little-endian','trainer_id_length':4,'functions':records,'naming_basis':origin['naming_basis'],'raw_rom_bytes_included':False}
   map_path=Path(f'analysis/{rid}-trainer-id-map.json');write_json(root/map_path,mapping);is_origin=False
  outputs.extend([map_path,*cfg_paths]);releases.append({'id':rid,'language':rel['language'],'revision':rel['revision'],'build_kind':rel['build_kind'],'sha256':sha,'origin_reference':is_origin,'evidence':{'map':map_path.as_posix(),'cfgs':[p.as_posix() for p in cfg_paths]},'functions':mapping['functions']})
 summary={'schema_version':1,'game':game,'origin_reference':'Japanese','release_count':len(releases),'variant':origin['variant'],'functions':[x[0] for x in signatures],'releases':releases,'raw_rom_bytes_included':False};summary_path=Path('analysis/trainer-id-catalog-summary.json');write_json(root/summary_path,summary);outputs.append(summary_path)
 report_path=Path('research/trainer-id-catalog-reconstruction.md');languages=', '.join(dict.fromkeys(x['language'] for x in releases));(root/report_path).write_text(f"# {game} trainer-ID release catalog reconstruction\n\nThe existing Japanese reconstruction is the origin reference. Its verified function ranges were matched against every cataloged ROM without publishing the signatures. All {len(releases)} releases ({languages}) contain one unique, adjacent helper sequence with identical function hashes and publication-safe Thumb control-flow evidence.\n\nThe helpers preserve the four-byte little-endian trainer-ID representation. ROM instruction bytes are not included.\n",encoding='utf-8',newline='\n');outputs.append(report_path)
 test_path=Path('tests/test_trainer_id_catalog_reconstruction.py');outputs.append(test_path);missing=[p.as_posix() for p in outputs if not(root/p).is_file()]
 if missing:raise ValueError('missing output(s): '+', '.join(missing))
 manifest={'schema_version':1,'game':game,'origin_reference':'Japanese','release_count':len(releases),'generator':{'repository':'SakuraiTsubaki/Decompilation','tool':'tools/trainer_id_matrix_evidence.py','tool_sha256':file_hash(Path(__file__))},'outputs':[{'path':p.as_posix(),'sha256':file_hash(root/p)}for p in outputs],'raw_rom_bytes_included':False};write_json(root/'manifests/trainer-id-catalog-reconstruction.json',manifest)
 return summary
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--rom-dir',type=Path,required=True);p.add_argument('--catalog',type=Path,default=Path('analysis/global-release-catalog.json'));p.add_argument('--origin-map',type=Path,required=True);p.add_argument('--game',required=True);a=p.parse_args()
 try:build(a.root,a.rom_dir,a.catalog,a.origin_map,a.game)
 except(OSError,KeyError,ValueError,json.JSONDecodeError)as e:p.error(str(e))
 return 0
if __name__=='__main__':raise SystemExit(main())
