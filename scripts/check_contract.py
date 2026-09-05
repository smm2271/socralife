"""Check canonical references and UI whitelist without starting services."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
doc=json.loads((ROOT/'contracts/openapi.yaml').read_text(encoding='utf-8'))
def walk(value):
    if isinstance(value,dict):
        if '$ref' in value:
            target=doc
            for part in value['$ref'][2:].split('/'):target=target[part]
        for item in value.values():walk(item)
    elif isinstance(value,list):
        for item in value:walk(item)
walk(doc)
schema=json.loads((ROOT/'contracts/ui.schema.json').read_text(encoding='utf-8'))
assert len(schema['oneOf'])==9
assert all(v['additionalProperties'] is False for v in schema['oneOf'])
assert len({v['properties']['type']['const'] for v in schema['oneOf']})==9
print(f"Contract valid: {sum(len(p) for p in doc['paths'].values())} operations; 9 UI variants")
