#!/usr/bin/env python3
"""Analyze snapshot.json structure and data quality."""
import json
from datetime import datetime, timedelta
from collections import Counter

with open('/Users/jadenli/CodeSpace/llm-radar.jaden.tech/data/snapshot.json') as f:
    data = json.load(f)

print(f"Version: {data['version']}")
print(f"Generated: {data['generated_at']}")
print(f"Period: {data['period']}")
print(f"Mode: {data['execution_mode']}")
print()

for k in data:
    if isinstance(data[k], list):
        print(f"  {k}: {len(data[k])} entries")
    elif isinstance(data[k], dict):
        print(f"  {k}: {len(data[k])} entities")

providers = data.get('providers', [])
print(f"\n=== Providers ({len(providers)}) ===")

hl = Counter(p.get('hot_level','?') for p in providers)
print(f"Hot levels: {dict(hl)}")

now = datetime.fromisoformat(data['generated_at'])
c24 = now - timedelta(days=1)
c7 = now - timedelta(days=7)
r24, r17, r7p = 0, 0, 0
stale_entries = []
for p in providers:
    ds = p.get('last_event_date','')
    if ds:
        d = datetime.fromisoformat(ds)
        if d >= c24: r24 += 1
        elif d >= c7: r17 += 1
        else:
            r7p += 1
            stale_entries.append((p['name'], ds, p['last_event'][:60]))
print(f"Recency: 24h={r24}, 1-7d={r17}, >7d={r7p}")
for name, ds, ev in stale_entries:
    print(f"  STALE {name}: {ds} - {ev}")

conf = Counter(p.get('confidence','unknown') for p in providers)
print(f"\nConfidence: {dict(conf)}")

print("\n=== Missing fields ===")
for p in providers:
    issues = []
    if not p.get('key_people'): issues.append('no_kp')
    if not p.get('focus_areas'): issues.append('no_fa')
    if p.get('confidence') in ('low',''): issues.append('low_conf')
    if issues:
        print(f"  {p['name']}: {', '.join(issues)}")

print("\n=== URL quality ===")
for p in providers:
    u = p.get('last_event_url','')
    if not u: print(f"  EMPTY {p['name']}")
    elif '...' in u: print(f"  TRUNCATED {p['name']}: {u}")
    elif u in ('https://www.jiqizhixin.com','https://www.qbitai.com'): print(f"  BARE_DOMAIN {p['name']}: {p['last_event'][:50]}")

print("\n=== All providers by hot_score ===")
for p in sorted(providers, key=lambda x: x.get('hot_score',0), reverse=True):
    print(f"  {p.get('hot_score',0):3d} [{p.get('hot_level',''):4s}] {p['name']:20s} {p.get('last_event_date',''):10s}  {p['last_event'][:55]}")

for sec in ['people','tools','hotspots','llms']:
    if sec in data:
        items = data[sec]
        print(f"\n{sec}: {len(items)} entries")
        if items:
            print(f"  First: {items[0]}")
            print(f"  Last:  {items[-1]}")
