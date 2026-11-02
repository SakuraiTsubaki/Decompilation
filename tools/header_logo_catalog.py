#!/usr/bin/env python3
"""Decode and catalog the fixed GBA header Nintendo logo across releases."""
from __future__ import annotations
import argparse,hashlib,json,struct,zlib
from pathlib import Path

LOGO_OFFSET=0x04
LOGO_SIZE=156
WIDTH=104
HEIGHT=16
SCALE=4
EXPECTED_LOGO_SHA256="08a0153cfd6b0ea54b938f7d209933fa849da0d56f5a34c481060c9ff2fad818"
EXPECTED_PNG_SHA256="f07daf6e489d64b7e2bbf80c7f23104dece36e88e706ee8a779790f6e8377a8b"
BIOS_HUFFMAN_HEADER=bytes((0x24,0xD4,0,0,0x0F,0x40,0,0,0,1,0x81,0x82,0x82,0x83,0x0F,0x83,0x0C,0xC3,3,0x83,1,0x83,4,0xC3,8,0x0E,2,0xC2,0x0D,0xC2,7,0x0B,6,0x0A,5,9))
def digest(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def file_hash(path:Path)->str:return digest(path.read_bytes())
def write_json(path:Path,value:object)->None:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(value,indent=2)+"\n",encoding="utf-8",newline="\n")
def rom_index(directory:Path)->dict[str,Path]:
 out={}
 for p in directory.iterdir():
  if p.is_file()and p.suffix.lower()==".gba":out.setdefault(file_hash(p),p)
 return out
def chunk(kind:bytes,payload:bytes)->bytes:
 body=kind+payload;return struct.pack(">I",len(payload))+body+struct.pack(">I",zlib.crc32(body)&0xFFFFFFFF)
def huffman_decode(encoded:bytes)->bytes:
 header=int.from_bytes(encoded[:4],"little");symbol_bits=header&15;output_size=header>>8
 if symbol_bits not in(4,8):raise ValueError("unsupported BIOS Huffman symbol width")
 tree_root=5;code_pos=4+((encoded[4]+1)<<1);tree_pos=tree_root;output=bytearray(output_size);output_pos=decoded_bits=code_bits=code=0
 while output_pos<output_size:
  if code_bits==0:
   if code_pos+4>len(encoded):raise ValueError("truncated GBA logo Huffman stream")
   code=int.from_bytes(encoded[code_pos:code_pos+4],"little");code_pos+=4;code_bits=32
  code_bits-=1;branch=(code>>code_bits)&1;node=encoded[tree_pos];increment=((node&0x3F)+1)<<1
  if tree_pos&1:increment-=1
  tree_pos+=increment+branch
  if tree_pos>=len(encoded):raise ValueError("invalid GBA logo Huffman tree")
  if(node<<branch)&0x80:
   output[output_pos]|=encoded[tree_pos]<<decoded_bits;decoded_bits+=symbol_bits
   if decoded_bits==8:output_pos+=1;decoded_bits=0
   tree_pos=tree_root
 return bytes(output)
def cumulative_decode(encrypted:bytes)->bytes:
 if len(encrypted)<4:raise ValueError("truncated cumulative stream")
 output_size=int.from_bytes(encrypted[:4],"little")>>8
 if output_size!=WIDTH*HEIGHT//8:raise ValueError("unexpected decoded logo size")
 output=bytearray(output_size);total=0
 for out_pos,in_pos in zip(range(0,output_size,2),range(4,len(encrypted),2)):
  if in_pos+2>len(encrypted):raise ValueError("truncated cumulative stream")
  total=(total+int.from_bytes(encrypted[in_pos:in_pos+2],"little"))&0xFFFF;output[out_pos:out_pos+2]=total.to_bytes(2,"little")
 return bytes(output)
def decode_logo(logo:bytes)->bytes:
 if len(logo)!=LOGO_SIZE:raise ValueError("GBA header logo must be 156 bytes")
 return cumulative_decode(huffman_decode(BIOS_HUFFMAN_HEADER+logo))
def render_logo(logo:bytes)->bytes:
 decoded=decode_logo(logo);rows=[]
 for y in range(HEIGHT):
  logical=[]
  for x in range(WIDTH):
   tile_x,pixel_x=divmod(x,8);tile_y,pixel_y=divmod(y,8);bit_index=(tile_y*(WIDTH//8)+tile_x)*64+pixel_y*8+pixel_x;bit=(decoded[bit_index//8]>>(bit_index%8))&1;logical.append(0 if bit else 255)
  scan=b"\0"+b"".join(bytes((v,v,v,255))*SCALE for v in logical);rows.extend([scan]*SCALE)
 ihdr=struct.pack(">IIBBBBB",WIDTH*SCALE,HEIGHT*SCALE,8,6,0,0,0);return b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",ihdr)+chunk(b"IDAT",zlib.compress(b"".join(rows),9))+chunk(b"IEND",b"")
def extract(data:bytes,expected_sha256:str)->tuple[bytes,dict]:
 if digest(data)!=expected_sha256:raise ValueError("ROM SHA-256 mismatch")
 logo=data[LOGO_OFFSET:LOGO_OFFSET+LOGO_SIZE]
 if len(logo)!=LOGO_SIZE:raise ValueError("ROM is too short for header logo")
 png=render_logo(logo);return png,{"source_offset":LOGO_OFFSET,"source_length":LOGO_SIZE,"source_sha256":digest(logo),"decoded_1bpp_sha256":digest(decode_logo(logo)),"format":"gba-bios-huffman-plus-cumulative-104x16-1bpp-tiled","logical_width":WIDTH,"logical_height":HEIGHT,"png_width":WIDTH*SCALE,"png_height":HEIGHT*SCALE,"nearest_neighbor_scale":SCALE,"png_sha256":digest(png),"raw_rom_bytes_included":False}
def build(root:Path,rom_dir:Path,catalog_path:Path,game:str)->dict:
 catalog=json.loads((root/catalog_path).read_text(encoding="utf-8"));releases=catalog["releases"]
 if not releases or releases[0]["language"]!="Japanese":raise ValueError("catalog must begin with Japanese origin")
 roms=rom_index(rom_dir);png_path=Path("graphics/header/nintendo-logo.png");maps=[];records=[];canonical=None
 for index,release in enumerate(releases):
  rid,sha256=release["id"],release["sha256"]
  if sha256 not in roms:raise ValueError(f"missing catalog ROM: {rid}")
  png,report=extract(roms[sha256].read_bytes(),sha256)
  if report["source_sha256"]!=EXPECTED_LOGO_SHA256 or report["png_sha256"]!=EXPECTED_PNG_SHA256:raise ValueError(f"header logo differs: {rid}")
  if canonical is None:canonical=png;(root/png_path).parent.mkdir(parents=True,exist_ok=True);(root/png_path).write_bytes(png)
  elif png!=canonical:raise ValueError(f"rendered logo differs: {rid}")
  evidence={"schema_version":1,"axis":"Decompilation","target":{"release":rid,"language":release["language"],"revision":release["revision"],"build_kind":release["build_kind"],"sha256":sha256},"origin_reference":index==0,"asset":{"name":"GbaHeaderNintendoLogo",**report},"output":{"path":png_path.as_posix(),"sha256":digest(png)},"standard_location":"GBA cartridge header 0x000004..0x00009F","raw_rom_bytes_included":False};map_path=Path(f"analysis/{rid}-header-logo.json");write_json(root/map_path,evidence);maps.append(map_path);records.append({"id":rid,"language":release["language"],"revision":release["revision"],"build_kind":release["build_kind"],"sha256":sha256,"origin_reference":index==0,"source_sha256":report["source_sha256"],"png_sha256":report["png_sha256"],"evidence":map_path.as_posix()})
 summary={"schema_version":1,"axis":"Decompilation","game":game,"asset":"GbaHeaderNintendoLogo","origin_reference":releases[0]["id"],"release_count":len(records),"source_sha256":EXPECTED_LOGO_SHA256,"png":png_path.as_posix(),"png_sha256":EXPECTED_PNG_SHA256,"releases":records,"raw_rom_bytes_included":False};summary_path=Path("analysis/header-logo-summary.json");write_json(root/summary_path,summary)
 languages=", ".join(dict.fromkeys(x["language"]for x in records));research_path=Path("research/header-logo-reconstruction.md");(root/research_path).write_text(f"# {game} GBA header Nintendo logo reconstruction\n\n`{releases[0]['id']}` is the Japanese origin reference. Every one of the {len(records)} cataloged builds ({languages}) has the same 156-byte payload at header offset `0x04`. BIOS Huffman and cumulative-delta decoding independently reproduces the shared 104x16 logical logo and deterministic 416x64 PNG. Per-build reports retain ROM identity, source, decoded 1bpp, and PNG hashes without publishing ROM bytes.\n",encoding="utf-8",newline="\n")
 test_path=Path("tests/test_header_logo_reconstruction.py");outputs=[catalog_path,png_path,summary_path,*maps,research_path,test_path];missing=[p.as_posix()for p in outputs if not(root/p).is_file()]
 if missing:raise ValueError("missing output(s): "+", ".join(missing))
 write_json(root/"manifests/header-logo-reconstruction.json",{"schema_version":1,"axis":"Decompilation","game":game,"asset":"GbaHeaderNintendoLogo","origin_reference":releases[0]["id"],"release_count":len(records),"generator":{"repository":"SakuraiTsubaki/Decompilation","tool":"tools/header_logo_catalog.py","tool_sha256":file_hash(Path(__file__))},"outputs":[{"path":p.as_posix(),"sha256":file_hash(root/p)}for p in outputs],"raw_rom_bytes_included":False});return summary
def main()->int:
 p=argparse.ArgumentParser(description=__doc__);p.add_argument("--root",type=Path,required=True);p.add_argument("--rom-dir",type=Path,required=True);p.add_argument("--catalog",type=Path,default=Path("analysis/global-release-catalog.json"));p.add_argument("--game",required=True);a=p.parse_args()
 try:build(a.root,a.rom_dir,a.catalog,a.game)
 except(OSError,KeyError,ValueError,json.JSONDecodeError)as e:p.error(str(e))
 return 0
if __name__=="__main__":raise SystemExit(main())
