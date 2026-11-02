#!/usr/bin/env python3
"""Extract a reproducible species sprite set from RSE release catalogs."""
from __future__ import annotations
import argparse,hashlib,json,math,struct,zlib
from pathlib import Path

ROM_BASE=0x08000000
ENTRY_SIZE=8
FRONT_TO_BACK=0x14A0
BACK_TO_PALETTE=0x0DC0
REFERENCES={"Ruby":("pret/pokeruby","5784633ce4ef7ade1a7f2d2d0c288e3d5e6cdd7f"),"Sapphire":("pret/pokeruby","5784633ce4ef7ade1a7f2d2d0c288e3d5e6cdd7f"),"Emerald":("pret/pokeemerald","fe1d8e51b265851676b65885818b1f5f62586135")}
def digest(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def file_hash(path:Path)->str:return digest(path.read_bytes())
def write_json(path:Path,value:object)->None:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8",newline="\n")
def rom_index(directory:Path)->dict[str,Path]:
 out={}
 for p in directory.iterdir():
  if p.is_file()and p.suffix.lower()==".gba":out.setdefault(file_hash(p),p)
 return out
def decompress(data:bytes,offset:int)->tuple[bytes,int]:
 if offset+4>len(data)or data[offset]!=0x10:raise ValueError("missing GBA LZ77 header")
 size=int.from_bytes(data[offset+1:offset+4],"little");out=bytearray();cursor=offset+4
 while len(out)<size:
  if cursor>=len(data):raise ValueError("truncated LZ77 flags")
  flags=data[cursor];cursor+=1
  for bit in range(7,-1,-1):
   if len(out)>=size:break
   if flags&(1<<bit):
    if cursor+2>len(data):raise ValueError("truncated LZ77 token")
    a,b=data[cursor],data[cursor+1];cursor+=2;length=(a>>4)+3;distance=(((a&15)<<8)|b)+1
    if distance>len(out):raise ValueError("invalid LZ77 lookback")
    for _ in range(length):
     if len(out)>=size:break
     out.append(out[-distance])
   else:
    if cursor>=len(data):raise ValueError("truncated LZ77 literal")
    out.append(data[cursor]);cursor+=1
 return bytes(out),cursor-offset
def palette(raw:bytes)->tuple[bytes,list[tuple[int,int,int]]]:
 if len(raw)!=32:raise ValueError("species palette must contain 16 BGR555 colors")
 colors=[]
 for i in range(16):
  value=int.from_bytes(raw[i*2:i*2+2],"little");colors.append(tuple(((value>>shift)&31)*255//31 for shift in(0,5,10)))
 text=("JASC-PAL\n0100\n16\n"+"".join(f"{r} {g} {b}\n"for r,g,b in colors)).encode("ascii");return text,colors
def chunk(kind:bytes,payload:bytes)->bytes:return struct.pack(">I",len(payload))+kind+payload+struct.pack(">I",zlib.crc32(kind+payload))
def render(raw:bytes,colors:list[tuple[int,int,int]],scale:int=2)->bytes:
 if len(raw)!=0x800:raise ValueError("species sprite must decode to 0x800 bytes")
 width=height=64;pixels=[[0]*width for _ in range(height)]
 for tile in range(64):
  tx,ty=tile%8,tile//8
  for n,value in enumerate(raw[tile*32:tile*32+32]):
   y=n//4;x=(n%4)*2;pixels[ty*8+y][tx*8+x]=value&15;pixels[ty*8+y][tx*8+x+1]=value>>4
 scan=[]
 for row in pixels:
  line=b"\0"+bytes(channel for value in row for _ in range(scale)for channel in colors[value]);scan.extend([line]*scale)
 ihdr=struct.pack(">IIBBBBB",width*scale,height*scale,8,2,0,0,0);return b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",ihdr)+chunk(b"IDAT",zlib.compress(b"".join(scan),9))+chunk(b"IEND",b"")
def decoded_length(data:bytes,offset:int)->int:
 return int.from_bytes(data[offset+1:offset+4],"little")if 0<=offset+4<=len(data)and data[offset]==0x10 else-1
def locate_tables(data:bytes,species:int)->tuple[dict,dict,dict]:
 sprites=[];palettes=[]
 def matching_entries(metadata:bytes,decoded:int):
  cursor=0
  while True:
   pos=data.find(metadata,cursor)
   if pos<0:return
   entry=pos-4;cursor=pos+1
   if entry<0 or entry%4:continue
   source=int.from_bytes(data[entry:entry+4],"little")-ROM_BASE;table=entry-species*ENTRY_SIZE
   if table>=0 and decoded_length(data,source)==decoded:yield entry,table,source
 for entry,table,source in matching_entries((0x800).to_bytes(2,"little")+species.to_bytes(2,"little"),0x800):sprites.append({"entry_offset":entry,"table_offset":table,"source_offset":source,"size":0x800,"tag":species})
 for entry,table,source in matching_entries(species.to_bytes(2,"little")+b"\0\0",32):palettes.append({"entry_offset":entry,"table_offset":table,"source_offset":source,"tag":species})
 pairs=[(a,b)for a in sprites for b in sprites if b["table_offset"]-a["table_offset"]==FRONT_TO_BACK]
 if len(pairs)!=1:raise ValueError(f"expected one front/back table pair, found {len(pairs)}")
 front,back=pairs[0];normal=[p for p in palettes if p["table_offset"]-back["table_offset"]==BACK_TO_PALETTE]
 if len(normal)!=1:raise ValueError(f"expected one normal palette table, found {len(normal)}")
 return front,back,normal[0]
def source_text(species:int,name:str)->str:
 return f'''    .syntax unified
    .thumb

    .equ SPECIES_{name.upper()}, {species}

    @ Verified RSE table layouts used by the reconstruction assets.
    .macro CompressedSpriteSheet data, size, tag
    .word \\data
    .hword \\size, \\tag
    .endm

    .macro CompressedSpritePalette data, tag
    .word \\data
    .hword \\tag, 0
    .endm
'''
def extraction(data:bytes,offset:int,expected:int)->tuple[bytes,dict]:
 raw,used=decompress(data,offset)
 if len(raw)!=expected:raise ValueError(f"decoded length differs: {len(raw)}")
 return raw,{"source_offset":offset,"compressed_length":used,"compressed_sha256":digest(data[offset:offset+used]),"decompressed_length":len(raw),"decompressed_sha256":digest(raw),"raw_rom_bytes_included":False}
def build(root:Path,rom_dir:Path,catalog_path:Path,game:str,species:int,species_name:str)->dict:
 catalog=json.loads((root/catalog_path).read_text(encoding="utf-8"));releases=catalog["releases"]
 if not releases or releases[0]["language"]!="Japanese":raise ValueError("catalog must begin with Japanese origin")
 source_path=Path(f"src/{species_name}_species_sprite_tables.asm");(root/source_path).write_text(source_text(species,species_name),encoding="utf-8",newline="\n");roms=rom_index(rom_dir);repository,commit=REFERENCES[game];maps=[];assets=[];records=[]
 for index,release in enumerate(releases):
  rid,sha256=release["id"],release["sha256"]
  if sha256 not in roms:raise ValueError(f"missing catalog ROM: {rid}")
  data=roms[sha256].read_bytes();front,back,pal=locate_tables(data,species);front_raw,front_report=extraction(data,front["source_offset"],0x800);back_raw,back_report=extraction(data,back["source_offset"],0x800);pal_raw,pal_report=extraction(data,pal["source_offset"],32);pal_bytes,colors=palette(pal_raw);front_png=render(front_raw,colors);back_png=render(back_raw,colors)
  base=Path("graphics/pokemon");front_path=base/f"{species_name}-front-{rid}.png";back_path=base/f"{species_name}-back-{rid}.png";palette_path=base/f"{species_name}-{rid}.pal"
  for path,payload in((front_path,front_png),(back_path,back_png),(palette_path,pal_bytes)):(root/path).parent.mkdir(parents=True,exist_ok=True);(root/path).write_bytes(payload);assets.append(path)
  evidence={"schema_version":1,"axis":"Decompilation","target":{"release":rid,"sha256":sha256,"build_kind":release["build_kind"]},"origin_reference":index==0,"species":{"id":species,"name":species_name},"source":source_path.as_posix(),"source_sha256":file_hash(root/source_path),"discovery":{"front_to_back_table_delta":FRONT_TO_BACK,"back_to_palette_table_delta":BACK_TO_PALETTE,"front":front,"back":back,"palette":pal},"outputs":[{"path":front_path.as_posix(),"sha256":digest(front_png),"extraction":front_report},{"path":back_path.as_posix(),"sha256":digest(back_png),"extraction":back_report},{"path":palette_path.as_posix(),"sha256":digest(pal_bytes),"extraction":pal_report}],"naming_basis":{"repository":repository,"commit":commit,"paths":["src/data/pokemon_graphics/front_pic_table.h","src/data/pokemon_graphics/back_pic_table.h","src/data/pokemon_graphics/palette_table.h"]},"raw_rom_bytes_included":False}
  map_path=Path(f"analysis/{rid}-{species_name}-sprite-set.json");write_json(root/map_path,evidence);maps.append(map_path);records.append({"id":rid,"language":release["language"],"revision":release["revision"],"build_kind":release["build_kind"],"sha256":sha256,"origin_reference":index==0,"evidence":map_path.as_posix(),"front":front_path.as_posix(),"back":back_path.as_posix(),"palette":palette_path.as_posix()})
 summary={"schema_version":1,"axis":"Decompilation","game":game,"species":{"id":species,"name":species_name},"origin_reference":releases[0]["id"],"release_count":len(records),"releases":records,"raw_rom_bytes_included":False};summary_path=Path(f"analysis/{species_name}-sprite-set-summary.json");write_json(root/summary_path,summary)
 languages=", ".join(dict.fromkeys(x["language"]for x in records));research_path=Path(f"research/{species_name}-sprite-set.md");(root/research_path).write_text(f"# {game} {species_name.title()} sprite reconstruction\n\n`{releases[0]['id']}` is the Japanese origin reference. All {len(records)} cataloged builds ({languages}) independently locate the species front, back, and normal-palette tables by their structural deltas. Each GBA LZ77 stream is decoded, rendered to a 128x128 PNG with the verified BGR555 palette, and recorded with compressed, decoded, palette, and output hashes. No ROM bytes are published.\n",encoding="utf-8",newline="\n")
 test_path=Path(f"tests/test_{species_name}_sprite_reconstruction.py");outputs=[catalog_path,source_path,summary_path,*maps,*assets,research_path,test_path];missing=[p.as_posix()for p in outputs if not(root/p).is_file()]
 if missing:raise ValueError("missing output(s): "+", ".join(missing))
 write_json(root/f"manifests/{species_name}-sprite-reconstruction.json",{"schema_version":1,"axis":"Decompilation","game":game,"species":{"id":species,"name":species_name},"origin_reference":releases[0]["id"],"release_count":len(records),"generator":{"repository":"SakuraiTsubaki/Decompilation","tool":"tools/rse_species_sprite_catalog.py","tool_sha256":file_hash(Path(__file__))},"outputs":[{"path":p.as_posix(),"sha256":file_hash(root/p)}for p in outputs],"raw_rom_bytes_included":False});return summary
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,required=True);p.add_argument("--rom-dir",type=Path,required=True);p.add_argument("--catalog",type=Path,default=Path("analysis/global-release-catalog.json"));p.add_argument("--game",choices=sorted(REFERENCES),required=True);p.add_argument("--species",type=int,required=True);p.add_argument("--species-name",required=True);a=p.parse_args()
 try:build(a.root,a.rom_dir,a.catalog,a.game,a.species,a.species_name)
 except(OSError,KeyError,ValueError,json.JSONDecodeError)as e:p.error(str(e))
 return 0
if __name__=="__main__":raise SystemExit(main())
