"""Generate shared DTOs from the committed contract; --check detects drift."""
import json, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
schemas=json.loads((ROOT/'contracts/openapi.yaml').read_text(encoding='utf-8'))['components']['schemas']
def pytype(s):
    if '$ref' in s:return s['$ref'].split('/')[-1]
    if 'anyOf' in s:return ' | '.join(pytype(x) for x in s['anyOf'])
    if 'enum' in s:return 'Literal['+', '.join(repr(x) for x in s['enum'])+']'
    t=s.get('type')
    if t=='array':return 'list['+pytype(s['items'])+']'
    return {'string':'str','integer':'int','number':'float','boolean':'bool','null':'None','object':'dict[str, Any]'}.get(t,'Any')
def tstype(s):
    if '$ref' in s:return s['$ref'].split('/')[-1]
    if 'anyOf' in s:return ' | '.join(tstype(x) for x in s['anyOf'])
    if 'enum' in s:return ' | '.join(json.dumps(x) for x in s['enum'])
    if 'const' in s:return json.dumps(s['const'])
    t=s.get('type')
    if t=='array':return 'Array<'+tstype(s['items'])+'>'
    if t=='object' and 'properties' in s:return '{ '+ '; '.join(k+('' if k in s.get('required',[]) else '?')+': '+tstype(v) for k,v in s['properties'].items())+' }'
    return {'string':'string','integer':'number','number':'number','boolean':'boolean','null':'null','object':'Record<string, unknown>'}.get(t,'unknown')
py=['# Generated; edit contracts/openapi.yaml instead.','from __future__ import annotations','from typing import Any, Literal','from pydantic import BaseModel, ConfigDict, Field','','class ContractModel(BaseModel):','    model_config = ConfigDict(extra="forbid")','']
ts=['// Generated; edit contracts/openapi.yaml instead.']
for name,s in schemas.items():
    py.append('class '+name+'(ContractModel):')
    ts.append('export interface '+name+' {')
    for k,v in s['properties'].items():
        required=k in s.get('required',[]);pt=pytype(v)
        opts=[]
        for jk,pk in [('minLength','min_length'),('maxLength','max_length'),('minimum','ge'),('maximum','le')]:
            if jk in v:opts.append(f'{pk}={v[jk]!r}')
        if not required:
            if 'None' not in pt:pt+=' | None'
            opts.insert(0,'default=None')
        py.append('    '+k+': '+pt+(' = Field('+', '.join(opts)+')' if opts else ''))
        ts.append('  '+k+('' if required else '?')+': '+tstype(v)+';')
    if not s['properties']:py.append('    pass')
    py.append('');ts.append('}')
py += [f'{name}.model_rebuild()' for name in schemas]
ui=json.loads((ROOT/'contracts/ui.schema.json').read_text(encoding='utf-8'))
ts.append('export type UIComponent = '+' |\n'.join(tstype(x) for x in ui['oneOf'])+';')
outputs={ROOT/'backend/app/contracts.py':'\n'.join(py)+'\n',ROOT/'frontend/src/app/contracts.ts':'\n'.join(ts)+'\n'}
for path,content in outputs.items():
    if '--check' in sys.argv:
        if not path.exists() or path.read_text(encoding='utf-8')!=content:raise SystemExit('Contract drift: '+str(path))
    else:
        path.parent.mkdir(parents=True,exist_ok=True);path.write_text(content,encoding='utf-8')
