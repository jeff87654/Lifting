import json, os
m = json.load(open(r'C:/Users/jeffr/Downloads/Lifting/parallel_s15_m6m7_v2/manifest.json'))
root = r'C:/Users/jeffr/Downloads/Lifting/parallel_s15_m6m7_v2/'
missing = []
for k, v in m['partitions'].items():
    d = root + '[' + ','.join(str(x) for x in v['partition']) + ']'
    if not os.path.exists(d + '/summary.txt'):
        missing.append((k, v.get('status'), v.get('worker_id')))
for x in missing:
    print(x)
print('missing count:', len(missing))
