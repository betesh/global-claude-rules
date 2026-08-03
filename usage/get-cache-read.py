import json,sys
for l in open(sys.argv[1]):
    u=(json.loads(l).get('message') or {}).get('usage')
    if u: print(u.get('cache_creation_input_tokens'), u.get('cache_read_input_tokens')); break
