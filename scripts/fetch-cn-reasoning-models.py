#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""抓取并排序「中国境内可直连的推理模型」Top N（可复核：快照 sha 落盘）。

数据源（两个公开快照，均按 URL 抓取并记录 sha256）：
  1. https://models.dev/api.json            —— 价格 / 上下文 / reasoning / tool_call / provider 元数据
  2. https://artificialanalysis.ai/leaderboards/models —— AA 智能指数与分项（页面内 RSC payload）

产出（默认 documents/reports/）：
  · cn-reasoning-models-<date>.json   榜单 + 快照 sha + 口径
  · cn-reasoning-models-<date>.html   同数据的独立静态页（无外链、无 JS 依赖）

口径：
  · 境内 provider = 12 个厂商官方 / .cn 直连端点（见 CN_PROVIDERS）
  · 混合价 = (3×input + output) / 4（USD per 1M tokens，3:1 读写比）
  · 性价比 = 能力分 ÷ 混合价；榜 A 用 AA 官方指数，榜 B 用自建合成分（9 子项百分位均值），榜 C 只按价格档位（不冒充评分）
  · 仅收 reasoning=true + tool_call=true + 上下文 ≥128k

用法:
  python3 scripts/fetch-cn-reasoning-models.py [--date YYYYMMDD] [--top 20] [--out-dir documents/reports]
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import html
import json
import re
from datetime import date
from pathlib import Path

MODELS_DEV = 'https://models.dev/api.json'
AA_BOARD = 'https://artificialanalysis.ai/leaderboards/models'

CN_PROVIDERS = ['deepseek', 'alibaba-cn', 'moonshotai-cn', 'zhipuai', 'minimax-cn', 'stepfun',
                'volcengine', 'tencent-tokenhub', 'siliconflow-cn', 'modelscope', 'sensenova', 'xiaomi']

# AA 榜单里的名字与 models.dev 的 name 不完全一致 ⇒ 显式映射（只映射真实同名型号，不猜）
ALIAS = {
    'Kimi K3.1 Pro': 'Kimi K3.1 Pro', 'Qwen4 Max': 'Qwen3.8 Max', 'Tencent Hy4': 'Hy4',
    'DeepSeek V4.1 Flash 1017 (Max)': 'DeepSeek V4.1 Flash 1017',
    'DeepSeek V4.1 Flash 1017 (High)': 'DeepSeek V4.1 Flash 1017',
    'GLM-5.3 (Max)': 'GLM-5.3', 'GLM-5.3 (Low)': 'GLM-5.3',
    'MiMo-V2.6-Pro': 'MiMo-V2.6-Pro', 'MiMo-V2.6-Flash': 'MiMo-V2.6-Flash',
    'MiniMax-M3.1-Flash': 'MiniMax-M3.1-Flash', 'MiniMax-M3': 'MiniMax-M3',
    'Qwen3.8-Flash-Next': 'Qwen3.8 Flash', 'Step 5 Preview': 'Step 5 Preview',
    'GLM-5.3-Flash': 'GLM-5.3-Flash', 'DeepSeek V4 Pro 0813 (Max)': 'DeepSeek V4 Pro 0813',
    'DeepSeek V4 Pro 0813 (High)': 'DeepSeek V4 Pro 0813', 'Qwen3.8 27B (Xhigh)': 'Qwen3.8 27B',
    'Kimi K2.7 Code': 'Kimi K2.7 Code',
}
# 榜 B：AA 还没出官方指数的型号（用合成分）
TIER_B = {'Qwen3.5 397B A17B (Reasoning)': 'Qwen3.5 397B-A17B', 'Qwen3.7 Plus': 'Qwen3.7 Plus',
          'Kimi K2.7 Code': 'Kimi K2.7 Code'}
# 榜 C：AA 未测（能力列留空，只给价格档位）
TIER_C = [('Qwen3.7 Flash', 'alibaba-cn'), ('Step 3.5 Flash', 'stepfun'), ('GLM-4.7-FlashX', 'zhipuai')]
SUBS = ['hle-diamond', 'gpqa-diamond', 'terminalbench-4-0', 'scicode', 'frontiercode-2-0',
        'tau2-bench', 'artificial-analysis-long-context-reasoning', 'aa-briefcase',
        'gdpval-aa-normalized']
MIN_CTX = 131072


def fetch(url: str) -> bytes:
    import urllib.request
    req = urllib.request.Request(url, headers={'User-Agent': 'llm-radar-report/1.0'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def parse_aa(page: str):
    d = page
    for _ in range(4):
        d = d.replace('\\\\"', '"').replace('\\"', '"')
        if 'initialModels":[' in d:
            break
    i = d.find('initialModels":[')
    if i < 0:
        raise RuntimeError('AA 页面里找不到 initialModels（版式可能变了）')
    j = d.index('[', i)
    depth, instr, esc = 0, False, False
    end = None
    for k in range(j, len(d)):
        c = d[k]
        if instr:
            if esc:
                esc = False
            elif c == '\\':
                esc = True
            elif c == '"':
                instr = False
            continue
        if c == '"':
            instr = True
        elif c == '[':
            depth += 1
        elif c == ']':
            depth -= 1
            if depth == 0:
                end = k + 1
                break
    return json.loads(d[j:end])


def composite(models):
    dist = {k: sorted(m['scores'][k] for m in models if (m.get('scores') or {}).get(k) is not None)
            for k in SUBS}

    def pct(k, v):
        xs = dist[k]
        return 100.0 * bisect.bisect_left(xs, v) / max(1, len(xs))

    out = {}
    for m in models:
        sc = m.get('scores') or {}
        vals = [(k, sc[k]) for k in SUBS if sc.get(k) is not None]
        if len(vals) >= 4:
            out[m['name']] = round(sum(pct(k, v) for k, v in vals) / len(vals), 1)
    return out


def cn_offer(md, name, providers=CN_PROVIDERS):
    best = None
    for pid in providers:
        for mid, m in (md.get(pid, {}).get('models') or {}).items():
            if m.get('name') != name:
                continue
            cost = m.get('cost') or {}
            lim = m.get('limit') or {}
            if cost.get('input') is None or not m.get('tool_call'):
                continue
            if (lim.get('context') or 0) < MIN_CTX:
                continue
            blend = (3 * cost['input'] + cost['output']) / 4
            cand = dict(provider=pid, provider_name=md[pid].get('name', pid), model_id=mid,
                        input=cost['input'], output=cost['output'], blend=round(blend, 4),
                        context=lim.get('context'), release=m.get('release_date'),
                        open_weights=bool(m.get('open_weights')),
                        vision='image' in ((m.get('modalities') or {}).get('input') or []))
            if best is None or cand['blend'] < best['blend']:
                best = cand
    return best


def build(md, aa, top=20):
    comp = composite(aa)
    rows = []
    for m in aa:
        name = m.get('name')
        idx = m.get('intelligenceIndex') or 0
        if idx <= 0 or not m.get('isReasoning'):
            continue
        target = ALIAS.get(name)
        if not target:
            continue
        off = cn_offer(md, target)
        if not off:
            continue
        rows.append({**off, 'model': target, 'aa_name': name, 'tier': 'A',
                     'score': round(idx, 2), 'score_kind': 'AA 智能指数',
                     'value': round(idx / off['blend'], 1) if off['blend'] else None})
    seen, uniq = set(), []
    for r in sorted(rows, key=lambda x: -(x['value'] or 0)):
        if r['model'] in seen:
            continue
        seen.add(r['model'])
        uniq.append(r)
    for name, target in TIER_B.items():
        off = cn_offer(md, target)
        sc = comp.get(name)
        if not off or sc is None:
            continue
        uniq.append({**off, 'model': target, 'aa_name': name, 'tier': 'B', 'score': sc,
                     'score_kind': '自建合成分', 'value': round(sc / off['blend'], 1)})
    for model, pid in TIER_C:
        off = cn_offer(md, model, [pid])
        if not off:
            continue
        uniq.append({**off, 'model': model, 'aa_name': '', 'tier': 'C', 'score': None,
                     'score_kind': '未测评测', 'value': None})
    for i, r in enumerate(uniq[:top], 1):
        r['rank'] = i
    return uniq[:top]


def render_html(payload, out: Path):
    rows = payload['models']
    def fmt(v, nd=2):
        return '-' if v is None else f'{v:.{nd}f}'
    tr = []
    for r in rows:
        score = '未测' if r['score'] is None else (f"{r['score']:.2f}" if r['tier'] == 'A' else f"{r['score']:.1f}*")
        tr.append(f"""<tr class="t{r['tier']}">
  <td class="rk">{r['rank']}</td>
  <td class="nm"><b>{html.escape(r['model'])}</b>
      {' <span class="badge use">在用</span>' if r.get('in_use') else ''}
      {' <span class="badge ow">开源</span>' if r.get('open_weights') else ''}</td>
  <td>{html.escape(r['provider_name'])}</td>
  <td class="num">{score}</td>
  <td class="num">${fmt(r['input'],3)}</td>
  <td class="num">${fmt(r['output'],3)}</td>
  <td class="num">${fmt(r['blend'],3)}</td>
  <td class="num strong">{'-' if r['value'] is None else f"{r['value']:.1f}"}</td>
  <td class="num">{r['context']//1000}k</td>
</tr>""")
    doc = f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>中国境内可用推理模型 Top {len(rows)} · 性价比（{payload['date']}）</title>
<style>
:root{{--bg:#0b1020;--panel:#131a2e;--line:#26314d;--fg:#e6ebf5;--dim:#8b98b5;--accent:#5cc8ff;--hot:#ff6b6b}}
*{{box-sizing:border-box}}
body{{margin:0;padding:32px 20px 64px;background:linear-gradient(180deg,#080c18,#0b1020 40%);color:var(--fg);
font:14px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:1180px;margin:0 auto}}
h1{{font-size:26px;margin:0 0 6px}}
.sub{{color:var(--dim);font-size:13px;margin-bottom:22px}}
.kpi{{display:flex;gap:12px;flex-wrap:wrap;margin:0 0 22px}}
.kpi div{{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 14px;font-size:12px;color:var(--dim)}}
.kpi b{{display:block;color:var(--fg);font-size:18px;margin-top:2px}}
table{{width:100%;border-collapse:collapse;background:var(--panel);border:1px solid var(--line);border-radius:12px;overflow:hidden}}
th,td{{padding:9px 10px;border-bottom:1px solid var(--line);text-align:left;font-size:13px}}
th{{background:#0f1730;color:var(--dim);font-weight:600;font-size:12px;letter-spacing:.02em}}
tbody tr:hover{{background:#16203a}}
tr.tB td.rk{{color:#c9a227}} tr.tC td.rk{{color:var(--dim)}}
.rk{{width:34px;color:var(--accent);font-weight:700}}
.nm b{{font-weight:600}}
.num{{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}}
.strong{{color:var(--accent);font-weight:700}}
.badge{{font-size:10px;padding:1px 5px;border-radius:4px;vertical-align:middle;margin-left:4px}}
.badge.use{{background:#1c3a2a;color:#6ee7a8;border:1px solid #2f6b4c}}
.badge.ow{{background:#1c2a3a;color:#7dd3fc;border:1px solid #2c4a63}}
.note{{margin-top:22px;padding:16px 18px;background:var(--panel);border:1px solid var(--line);border-radius:12px;color:var(--dim);font-size:12.5px}}
.note b{{color:var(--fg)}}
code{{background:#0a1020;border:1px solid var(--line);padding:1px 5px;border-radius:4px;font-size:12px}}
footer{{margin-top:18px;color:#5d6a86;font-size:11.5px}}
</style></head><body><div class="wrap">
<h1>中国境内可用 · 推理模型性价比 Top {len(rows)}</h1>
<div class="sub">口径：混合价 =（3×输入 + 输出）/4，USD/百万 token；性价比 = 能力分 ÷ 混合价。
榜 A 用 Artificial Analysis 官方智能指数，榜 B 用自建合成分（9 子项百分位均值，标 *），榜 C 未测评测。</div>
<div class="kpi">
  <div>快照日期<b>{payload['date'][:4]}-{payload['date'][4:6]}-{payload['date'][6:]}</b></div>
  <div>境内渠道<b>{len(payload['providers'])}</b></div>
  <div>测试模型池<b>{payload['pool_size']}</b></div>
  <div>入榜<b>{len(rows)}</b></div>
  <div>models.dev 快照<b>{payload['sources']['models_dev']['sha256'][:12]}…</b></div>
  <div>AA 快照<b>{payload['sources']['aa_board']['sha256'][:12]}…</b></div>
</div>
<table><thead><tr>
  <th>#</th><th>模型</th><th>境内渠道</th><th>能力分</th><th>输入 $</th><th>输出 $</th><th>混合价</th><th>分/价</th><th>上下文</th>
</tr></thead><tbody>
{''.join(tr)}
</tbody></table>
<div class="note">
<b>怎么读：</b>「分/价」越高 = 单位成本换到的能力越多。榜 A 之间可直接横比；榜 B（*）与榜 C 与榜 A 不可直接比 ——
它们的差别是「有没有官方指数」，不是能力差距。<br>
<b>注意：</b>缓存读价未计入（DeepSeek 缓存读 $0.003/1M 会让真实账单低 30%–60%）；厂商包月 Token Plan 更便宜，未纳入。<br>
<b>可复核：</b>生成脚本 <code>scripts/fetch-cn-reasoning-models.py</code>，数据
<code>documents/reports/{payload['data_file']}</code>（含两个原始快照的 sha256）。
</div>
<footer>生成于 {payload['generated_at']} · 来源 models.dev + artificialanalysis.ai</footer>
</div></body></html>
"""
    out.write_text(doc, encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--date', default=date.today().strftime('%Y%m%d'))
    ap.add_argument('--top', type=int, default=20)
    ap.add_argument('--out-dir', default='documents/reports')
    ap.add_argument('--in-use', default='', help='逗号分隔的「在用」模型名，用于页面标注')
    args = ap.parse_args()

    raw_md = fetch(MODELS_DEV)
    raw_aa = fetch(AA_BOARD)
    md = json.loads(raw_md)
    aa_page = raw_aa.decode('utf-8', 'replace')
    aa = parse_aa(aa_page)
    models = build(md, aa, top=args.top)
    in_use = {x.strip() for x in args.in_use.split(',') if x.strip()}
    for r in models:
        r['in_use'] = r['model'] in in_use

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = dict(
        date=args.date,
        generated_at=date.today().isoformat(),
        criteria=dict(providers=CN_PROVIDERS, blend='(3*input+output)/4', min_context=MIN_CTX,
                      require=dict(reasoning=True, tool_call=True)),
        sources={
            'models_dev': {'url': MODELS_DEV, 'bytes': len(raw_md), 'sha256': sha(raw_md)},
            'aa_board': {'url': AA_BOARD, 'bytes': len(raw_aa), 'sha256': sha(raw_aa)},
        },
        pool_size=len([m for m in aa if m.get('isReasoning')]),
        providers=CN_PROVIDERS,
        models=models,
    )
    data_file = f'cn-reasoning-models-{args.date}.json'
    payload['data_file'] = data_file
    (out_dir / data_file).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    render_html(payload, out_dir / f'cn-reasoning-models-v1.0-{args.date[:4]}-{args.date[4:6]}-{args.date[6:]}.html')

    print(f"[fetch] models.dev {len(raw_md)}B sha256={payload['sources']['models_dev']['sha256'][:16]}…")
    print(f"[fetch] AA board   {len(raw_aa)}B sha256={payload['sources']['aa_board']['sha256'][:16]}…")
    print(f"[rank]  入榜 {len(models)} 条 → {out_dir / data_file}")
    for r in models:
        print(f"  {r['rank']:2d} [{r['tier']}] {r['model'][:26]:26s} {r['provider']:16s} "
              f"score={r['score'] if r['score'] is not None else '-':>6} blend={r['blend']:.3f} "
              f"value={r['value'] if r['value'] is not None else '-'}")
    return 0


if __name__ == '__main__':
    from cli_interrupt import emit  # 唯一捕获点（§11.1-1）

    import sys
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        emit('python3 scripts/fetch-cn-reasoning-models.py', sys.argv)
