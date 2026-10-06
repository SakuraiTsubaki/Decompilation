#!/usr/bin/env python3
"""Validate a publication-safe GBA interrupt reconstruction address map."""
from __future__ import annotations
import argparse,json,re
def number(value):
    return int(value,0) if isinstance(value,str) else value
def validate(address_map:dict)->dict:
    target=address_map['target'];digest=target['sha256']
    if not re.fullmatch(r'[0-9a-fA-F]{64}',digest):raise ValueError('target SHA-256 is malformed')
    region=address_map['rom_code_and_literals']
    if region.get('raw_bytes_published') is not False:raise ValueError('raw ROM publication must be false')
    if not re.fullmatch(r'[0-9a-fA-F]{64}',region['sha256']):raise ValueError('range SHA-256 is malformed')
    start=0x08000000+number(region['start_offset']);end=0x08000000+number(region['end_offset_exclusive'])
    if start>=end or start&1 or end&1:raise ValueError('ROM range must be positive and halfword-aligned')
    functions=[]
    for item in address_map['functions']:
        lo=number(item['address']);hi=number(item['range_end_exclusive'])
        if not item.get('name'):raise ValueError('function name must be non-empty')
        if lo>=hi or lo&1 or hi&1:raise ValueError('function range must be positive and halfword-aligned')
        if not start<=lo<hi<=end:raise ValueError('function lies outside hashed ROM range')
        functions.append((lo,hi,item['name']))
    if functions!=sorted(functions):raise ValueError('functions must be ordered by address')
    if any(a[1]>b[0] for a,b in zip(functions,functions[1:])):raise ValueError('function ranges overlap')
    calls=[]
    for item in address_map.get('calls',[]):
        source=number(item['address']);target_address=number(item['target'])
        if not item.get('name'):raise ValueError('call name must be non-empty')
        if not any(lo<=source<hi for lo,hi,_ in functions):raise ValueError('call source is outside every function')
        if source&1 or target_address&1:raise ValueError('call addresses must be halfword-aligned')
        calls.append((source,target_address,item['name']))
    offsets=address_map.get('proven_offsets',{})
    if any(not isinstance(v,int) or v<0 for v in offsets.values()):raise ValueError('proven offsets must be nonnegative integers')
    if len(set(offsets.values()))!=len(offsets):raise ValueError('proven offsets must be unique')
    return {'schema_version':1,'release':target['release'],'source_sha256':digest.lower(),'function_count':len(functions),'call_count':len(calls),'functions':[name for _,_,name in functions],'range_start':start,'range_end_exclusive':end,'proven_offset_count':len(offsets),'raw_rom_bytes_included':False}
def main()->None:
    p=argparse.ArgumentParser();p.add_argument('address_map');p.add_argument('--report');a=p.parse_args()
    with open(a.address_map,encoding='utf-8') as f:report=validate(json.load(f))
    text=json.dumps(report,indent=2,sort_keys=True)+'\n'
    if a.report:
        with open(a.report,'w',encoding='utf-8',newline='\n') as f:f.write(text)
    else:print(text,end='')
if __name__=='__main__':main()

