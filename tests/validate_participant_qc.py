#!/usr/bin/env python3
"""Independent source-to-report validator; does not import participant_qc.

Reads only. Redirect stdout to retain a validation receipt. Cohort-size assertions
are optional, because later data deliveries may legitimately change the cohort.
"""
import argparse
import csv
import hashlib
import itertools
import json
import math
import re
import statistics
import subprocess
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = ['calibration_target','manual_target','near_chance_or_worse','anticipatory']
EXCLUSION = ['calibration_target','near_chance_or_worse','anticipatory']
BLOCKS = ['CALIBRATION','MANUAL','AUTOMATION1','AUTOMATION2']
ORDERS = list(itertools.permutations(BLOCKS[1:]))
META = ['participant_id','run_timestamp','run_id','selected_cohort','key_conflict','key_nonconf','main_block_order']


def read(path):
    with Path(path).open(newline='') as handle:
        return list(csv.DictReader(handle))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def missing(x):
    return x is None or str(x).strip().lower() in ('','na','nan')


def num(x):
    try:
        value = float(x)
        return value if math.isfinite(value) else None
    except (ValueError,TypeError):
        return None


def binary(x):
    return {'1':1,'0':0,'true':1,'false':0}.get(str(x).lower())


def near(actual, expected, label=''):
    if isinstance(expected,bool):
        assert str(actual).lower() == str(expected).lower(), (label, actual, expected)
    elif expected is None:
        assert missing(actual), (label, actual, expected)
    elif isinstance(expected,(float,int)):
        assert num(actual) is not None and math.isclose(float(actual),expected,rel_tol=1e-10,abs_tol=1e-10), (label,actual,expected)
    else:
        assert actual == expected, (label,actual,expected)


def same(a,b):
    return a == b or missing(a) and missing(b) or (num(a) is not None and num(b) is not None and math.isclose(float(a),float(b),rel_tol=1e-12,abs_tol=1e-12))


def group(rows):
    result = defaultdict(list)
    for r in rows:
        pid = int(r['participant_id'])
        assert pid > 0 and re.fullmatch(r'\d{8}_\d{6}',r['run_timestamp'])
        rid = f"p{pid:03d}_{r['run_timestamp']}"
        result[rid].append(r)
    for rid, rr in result.items():
        keys = [(int(r['block_idx']),int(r['trial_idx'])) for r in rr]
        assert len(keys) == len(set(keys)), ('duplicate identity',rid)
        rr.sort(key=lambda r:(int(r['block_idx']),int(r['trial_idx'])))
    return dict(sorted(result.items()))


def timeline(pid):
    order = ('CALIBRATION',)+ORDERS[(pid-1)%6]
    result = {}; start = 1
    for idx,code in enumerate(order,1):
        n = 300 if idx == 1 else 500
        result[code] = (idx,start,start+n-1)
        start += n
    return result


def trial_number(r):
    idx = int(r['block_idx'])
    return (0 if idx == 1 else 300+(idx-2)*500)+int(r['trial_idx'])


def timing_invalid(r):
    version = r.get('rt_timing_version')
    if missing(version):return False
    if version != 'ptb_queue_flip_v1':return True
    onset, stamp, ignored, delay = (num(r.get(k)) for k in ('stimulus_onset_s','response_timestamp_s','n_ignored_pre_onset_keydowns','response_readout_delay_s'))
    bad = missing(r.get('rt_backend_version')) or onset is None or ignored is None or ignored < 0 or ignored % 1 != 0
    if r['response'] in ('conflict','nonconflict'):
        rt = num(r['rt_s'])
        bad |= (onset is None or stamp is None or rt is None or stamp < onset
                or not math.isclose(stamp-onset,rt,rel_tol=1e-9,abs_tol=1e-8)
                or delay is None or delay < 0 or num(r['deadline_s']) is not None and rt >= num(r['deadline_s']))
    elif r['response'] == 'TIMEOUT':
        bad |= any(not missing(r.get(k)) for k in ('rt_s','response_timestamp_s','response_readout_delay_s'))
    return bool(bad)


def integrity(rows):
    pid = int(rows[0]['participant_id']); bounds = timeline(pid)
    index = {v[0]:k for k,v in bounds.items()}
    keys = ('D','J') if ((pid-1)//6)%2 == 0 else ('J','D')
    invalid, global_bad = set(), False
    for r in rows:
        block, trial = int(r['block_idx']), int(r['trial_idx'])
        if block not in index or not 1 <= trial <= (300 if block == 1 else 500):
            global_bad = True; continue
        code = index[block]
        answered = r['response'] in ('conflict','nonconflict'); timeout = r['response']=='TIMEOUT'
        correct = answered and r['response']==r['stimulus']
        bad = (r['block'] != code or (r['key_conflict'],r['key_nonconf']) != keys or num(r['deadline_s']) != 10
               or r['stimulus'] not in ('conflict','nonconflict') or not (answered or timeout))
        if answered:
            bad |= binary(r['correct']) != int(correct) or r['feedback'] != ('CORRECT' if correct else 'INCORRECT') or num(r['rt_s']) is None
        if timeout:
            bad |= (not missing(r['correct']) and binary(r['correct']) != 0) or r['feedback'] != 'TOO SLOW' or (not missing(r['rt_s']) and num(r['rt_s']) is None)
        if code.startswith('AUTOMATION'):
            advice = {'CONFLICT':'conflict','NON-CONF':'nonconflict'}.get(r['aid_label'])
            bad |= advice is None or binary(r['aid_correct']) != int(advice==r['stimulus']) or num(r['aid_accuracy_setting']) != (.95 if code=='AUTOMATION1' else .65)
        else:
            bad |= any(not missing(r[k]) for k in ('aid_label','aid_correct','aid_accuracy_setting'))
        bad |= not missing(r.get('is_PM')) and binary(r.get('is_PM')) != 0
        bad |= not missing(r.get('flash_onsets'))
        if bad:invalid.add(trial_number(r))
    return invalid,global_bad


def wilson(k,n,level):
    if not n:return None,None
    z = statistics.NormalDist().inv_cdf((1+level)/2)
    # Algebraically equivalent score-interval form, independently calculated.
    center = (k+z*z/2)/(n+z*z)
    radius = z*math.sqrt(k*(n-k)/n+z*z/4)/(n+z*z)
    return max(0,center-radius), min(1,center+radius)


def calculate(rows, expected, cfg, invalid, global_bad):
    rr = [r for r in rows if trial_number(r) in expected]
    assessable = not global_bad and not (expected & invalid) and {trial_number(r) for r in rr} == expected
    answered = [r for r in rr if r['response'] in ('conflict','nonconflict')]
    fast = [r for r in answered if num(r['rt_s']) is not None and float(r['rt_s']) < cfg['fast_rt_seconds']]
    k = sum(r['response']==r['stimulus'] for r in answered)
    fk = sum(r['response']==r['stimulus'] for r in fast)
    pos = [float(r['rt_s']) for r in answered if num(r['rt_s']) is not None and float(r['rt_s']) > 0]
    finite = [float(r['rt_s']) for r in answered if num(r['rt_s']) is not None]
    n = len(rr); nf = len(fast)
    low,high = wilson(k,n,cfg['interval_level']) if assessable else (None,None)
    fl,fh = wilson(fk,nf,cfg['interval_level']) if assessable else (None,None)
    result = dict(assessable=assessable,n_expected=len(expected),n_trials=n,n_answered=len(answered),
        n_timeouts=sum(r['response']=='TIMEOUT' for r in rr),n_correct=k if assessable else None,
        accuracy=k/n if assessable else None,accuracy_lower=low,accuracy_upper=high,
        n_fast=nf,fast_fraction=nf/n if assessable else None,n_fast_correct=fk if assessable else None,
        fast_accuracy=fk/nf if assessable and nf else None,fast_accuracy_lower=fl,fast_accuracy_upper=fh,
        n_nonpositive_rt=sum(x<=0 for x in finite),n_positive_fast=sum(float(r['rt_s'])>0 for r in fast),
        median_positive_rt_ms=statistics.median(pos)*1000 if pos else None,
        mean_answered_rt_ms=statistics.mean(finite)*1000 if finite else None,
        answered_accuracy=k/len(answered) if assessable and answered else None,
        n_timeouts_with_recorded_rt=sum(r['response']=='TIMEOUT' and num(r['rt_s']) is not None for r in rr),
        n_beyond_deadline=sum(num(r['rt_s']) is not None and num(r['deadline_s']) is not None and float(r['rt_s'])>float(r['deadline_s']) for r in answered),
        calibration_target_accuracy=.8,n_legacy_timing=sum(missing(r.get('rt_timing_version')) for r in rr),
        timing_versions='|'.join(sorted({'legacy_unspecified' if missing(r.get('rt_timing_version')) else r['rt_timing_version'] for r in rr})),
        n_timing_diagnostic_issues=sum(timing_invalid(r) for r in rr))
    result['timeout_fraction'] = result['n_timeouts']/n if assessable else None
    result['target_difference_pp'] = 100*(k/n-.8) if assessable else None
    for ms in cfg['sensitivity_thresholds_ms']:
        result[f'fraction_rt_lt_{ms}ms'] = sum(num(r['rt_s']) is not None and float(r['rt_s'])<ms/1000 for r in answered)/n if assessable else None
    return result


def scopes(rows,cfg):
    bounds = timeline(int(rows[0]['participant_id']))
    result = {code:set(range(bounds[code][1],bounds[code][2]+1)) for code in BLOCKS}
    result['aided_overall'] = result['AUTOMATION1'] | result['AUTOMATION2']
    result['experimental_overall'] = set(range(301,1801))
    result['calibration_tail'] = set(range(301-cfg['calibration_tail_n'],301))
    return result


def status(m,category,cfg):
    if not m['assessable']:return 'not_assessable'
    if category in ('calibration_target','manual_target'):
        flag = abs(m['target_difference_pp']) > cfg[category+'_band_pp']+1e-12
    elif category=='near_chance_or_worse':
        flag = m['accuracy'] <= cfg['chance_accuracy_max']+1e-12
    else:
        flag = (m['n_fast']>=cfg['fast_count_min'] and m['fast_fraction']>=cfg['fast_fraction_min']-1e-12
                and m['fast_accuracy'] is not None and m['fast_accuracy']<=cfg['fast_accuracy_max']+1e-12)
    return 'flag' if flag else 'clear'


def validate_metrics(out, runs, cfg, prefix='', summary_name='participant_summary.csv'):
    metric_rows = read(out/f'{prefix}scope_metrics.csv')
    exported = {(r['run_id'],r['scope']):r for r in metric_rows}
    assert len(exported)==len(metric_rows)==7*len(runs)
    checks = read(out/f'{prefix}screening_results.csv')
    check_map = {(r['run_id'],r['scope'],r['category']):r for r in checks}
    assert len(check_map)==len(checks)==14*len(runs)
    bin_rows = read(out/f'{prefix}trial_bin_summary.csv')
    bin_map = {(r['run_id'],int(r['trial_start'])):r for r in bin_rows}
    assert len(bin_map)==len(bin_rows)==sum(1800//cfg['bin_size'] for _ in runs)
    summaries = read(out/summary_name)
    assert len(summaries)==len(runs) and {s['run_id'] for s in summaries}==set(runs)
    summary_map = {s['run_id']:s for s in summaries}
    expected_metrics, expected_bins, expected_statuses, issues = {}, {}, {}, set()
    for rid, rows in runs.items():
        invalid, global_bad = integrity(rows)
        first = rows[0]; pid=int(first['participant_id'])
        meta = dict(participant_id=pid,run_timestamp=first['run_timestamp'],run_id=rid,selected_cohort=not bool(prefix),
                    key_conflict=first['key_conflict'],key_nonconf=first['key_nonconf'],main_block_order='|'.join(ORDERS[(pid-1)%6]))
        for k,v in meta.items():near(summary_map[rid][k],v,(rid,k))
        statuses = defaultdict(list); flags=[]; flag_exclusions=[]
        for scope, expected in scopes(rows,cfg).items():
            m = calculate(rows,expected,cfg,invalid,global_bad)
            expected_metrics[rid,scope] = m
            row = exported[rid,scope]
            for k,v in {**meta,**m,'trial_start':min(expected),'trial_end':max(expected)}.items():near(row[k],v,(rid,scope,k))
            assert bool(row['integrity_issues']) == (not m['assessable'])
            if not m['assessable']:issues.add((rid,scope))
            categories = ['calibration_target'] if scope=='calibration_tail' else ['near_chance_or_worse','anticipatory']
            if scope=='MANUAL':categories.append('manual_target')
            for category in categories:
                value = status(m,category,cfg)
                expected_statuses[rid,scope,category] = value
                c = check_map[rid,scope,category]
                assert c['status']==value,(rid,scope,category)
                near(c['use_for_exclusion'],category in EXCLUSION)
                for k,v in meta.items():near(c[k],v)
                for k in ('n_trials','accuracy','target_difference_pp','n_fast','fast_fraction','fast_accuracy'):near(c[k],m[k])
                statuses[category].append(value)
                if value=='flag':
                    flags.append(f'{category}:{scope}')
                    if category in EXCLUSION:flag_exclusions.append(f'{category}:{scope}')
        s = summary_map[rid]
        aggregate = {c:'flag' if 'flag' in vv else 'not_assessable' if 'not_assessable' in vv else 'clear' for c,vv in statuses.items()}
        for c,value in aggregate.items():assert s[c]==value
        incomplete=sum(v=='not_assessable' for vv in statuses.values() for v in vv)
        expected_summary=dict(n_flags=len(flags),n_not_assessable=incomplete,
            n_flagged_rules=sum(v=='flag' for v in aggregate.values()),flagged_any_rule=bool(flags),
            n_exclusion_rules=sum(aggregate[c]=='flag' for c in EXCLUSION),exclude_by_rules=bool(flag_exclusions),
            review_required=bool(flags) or incomplete>0,reasons='; '.join(flags),exclusion_reasons='; '.join(flag_exclusions))
        for k,v in expected_summary.items():near(s[k],v,(rid,k))
        for scope,(_,lo,hi) in timeline(pid).items():
            for start in range(lo,hi+1,cfg['bin_size']):
                expected = set(range(start,start+cfg['bin_size']))
                m = calculate(rows,expected,cfg,invalid,global_bad)
                mid=start+(cfg['bin_size']-1)/2
                expected_bins[rid,scope,mid-lo+1] = m
                b = bin_map[rid,start]
                for k,v in {**meta,**m,'scope':scope,'trial_start':start,'trial_end':max(expected),
                            'trial_midpoint':mid,'condition_trial_start':start-lo+1,'condition_trial_midpoint':mid-lo+1}.items():near(b[k],v,(rid,start,k))
    actual_issues=read(out/f'{prefix}integrity_issues.csv')
    assert {(r['run_id'],r['scope']) for r in actual_issues}==issues and len(actual_issues)==len(issues)
    return expected_metrics,expected_bins,summary_map,expected_statuses


class Links(HTMLParser):
    def __init__(self):super().__init__();self.paths=[];self.ids=set()
    def handle_starttag(self,tag,attrs):
        attrs=dict(attrs)
        self.paths.extend(attrs[k] for k in ('href','src') if k in attrs)
        if 'id' in attrs:self.ids.add(attrs['id'])


def check_artifact(path):
    if path.suffix=='.png':
        with Image.open(path) as im:im.verify()
        with Image.open(path) as im:assert im.width>=1000 and im.height>=700
    elif path.suffix=='.pdf':
        output=subprocess.check_output(['pdfinfo',str(path)],text=True)
        pages=int(re.search(r'^Pages:\s+(\d+)',output,re.M)[1]);assert pages>0
        return str(path.name),pages
    return None


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'analysis_outputs/semester1_2026_qc')
    parser.add_argument('--expect-current-cohort',action='store_true')
    args=parser.parse_args(argv);out=args.output_dir.resolve()
    manifest=json.loads((out/'manifest.json').read_text());cfg=json.loads((out/'config_snapshot.json').read_text())
    assert manifest['generator']=='atclab_participant_qc' and manifest['study']=='atclab_semester1_2026'
    assert manifest['exclusions_applied'] is False and manifest['qc_data_filtered'] is False
    assert (out/'COMPLETE.txt').exists()
    assert digest(manifest['input_csv'])==manifest['input_sha256']
    assert digest(manifest['config_path'])==manifest['config_sha256']
    assert json.loads(Path(manifest['config_path']).read_text())==cfg
    for item in manifest['sources']+manifest['raw_sources']:assert digest(item['path'])==item['sha256'],item['path']
    for item in manifest['outputs']:
        path=(out/item['path']).resolve();assert path.is_relative_to(out)
        assert path.stat().st_size==item['bytes'] and digest(path)==item['sha256'],item['path']
    assert {str(p.relative_to(out)) for p in out.rglob('*') if p.is_file() and p.name not in ('manifest.json','COMPLETE.txt')}=={r['path'] for r in manifest['outputs']}
    selected=group(read(manifest['input_csv']));raw={};inventory=read(out/'run_inventory.csv')
    assert len({int(rows[0]['participant_id']) for rows in selected.values()})==len(selected)
    raw_paths={str(p.resolve()) for p in Path(manifest['raw_dir']).glob('results_*_b00_ALL.csv')}
    assert raw_paths=={r['path'] for r in inventory}=={r['path'] for r in manifest['raw_sources']}
    for item in inventory:
        runs=group(read(item['path']));assert len(runs)==1
        rid,rows=next(iter(runs.items()));assert rid not in raw;raw[rid]=rows
        assert rid==item['run_id'] and digest(item['path'])==item['sha256']
        near(item['selected_cohort'],rid in selected);near(item['n_trials'],len(rows))
        near(item['participant_id'],int(rows[0]['participant_id']));assert item['run_timestamp']==rows[0]['run_timestamp']
    assert set(selected)<=set(raw)
    for rid,rr in selected.items():
        assert len(rr)==len(raw[rid])
        for a,b in zip(rr,raw[rid]):
            for k in set(a)|set(b):assert same(a.get(k),b.get(k)),(rid,k,a.get(k),b.get(k))
    selected_ids={int(v[0]['participant_id']):rid for rid,v in selected.items()}
    for item in inventory:
        pid=int(item['participant_id']);rid=item['run_id'];selected_rid=selected_ids.get(pid,'')
        assert item['selected_run_id']==selected_rid
        relation=('selected' if rid in selected else 'earlier' if selected_rid and item['run_timestamp']<selected[selected_rid][0]['run_timestamp'] else 'later' if selected_rid else 'no_selected_run')
        assert item['relation_to_selected']==relation
        repeated=sum(int(rr[0]['participant_id'])==pid for rr in raw.values())>1
        assert item['replacement_identity_status']==('unconfirmed' if repeated else 'no_repeated_id')
        assert item['historical_replacement_reason']=='not documented'
    historical={rid:rr for rid,rr in raw.items() if rid not in selected}
    metrics,bins,summaries,checks=validate_metrics(out,selected,cfg)
    hm,hb,hs,hc=validate_metrics(out,historical,cfg,'historical_','historical_run_summary.csv')
    near(manifest['selected_run_n'],len(selected));near(manifest['participant_n'],len(selected));near(manifest['historical_run_n'],len(historical))
    near(manifest['selected_trial_n'],sum(map(len,selected.values())));near(manifest['historical_trial_n'],sum(map(len,historical.values())))
    near(manifest['integrity_scope_n'],sum(not m['assessable'] for m in metrics.values()))
    near(manifest['historical_integrity_scope_n'],sum(not m['assessable'] for m in hm.values()))
    summary=json.loads((out/'exclusion_summary.json').read_text())
    candidates=sorted(int(s['participant_id']) for s in summaries.values() if binary(s['exclude_by_rules']))
    diagnostic=sorted(int(s['participant_id']) for s in summaries.values() if binary(s['flagged_any_rule']) and not binary(s['exclude_by_rules']))
    assert summary['participant_ids']==candidates and summary['diagnostic_only_participant_ids']==diagnostic
    near(summary['unique_flagged_n'],len(candidates));near(summary['unique_flagged_percent'],100*len(candidates)/len(selected))
    near(summary['remaining_if_applied_n'],len(selected)-len(candidates));near(manifest['unique_flagged_n'],len(candidates))
    assert summary['exclusions_applied'] is False and summary['qc_data_filtered'] is False
    assert summary['incomplete_assessment_ids']==sorted(int(s['participant_id']) for s in summaries.values() if int(s['n_not_assessable']))
    assert sorted(int(s['participant_id']) for s in read(out/'exclusion_candidates.csv'))==candidates
    for r in read(out/'exclusion_candidates.csv'):assert r==summaries[r['run_id']]
    actual_flags=read(out/'flagged_checks.csv')
    assert {(r['run_id'],r['scope'],r['category']) for r in actual_flags}=={k for k,v in checks.items() if v=='flag'}
    counts={r['criterion']:r for r in read(out/'exclusion_summary_table.csv')}
    for c in CATEGORIES:
        ids=sorted(int(s['participant_id']) for s in summaries.values() if s[c]=='flag')
        assert summary['rule_participant_ids'][c]==ids
        near(counts[c]['n'],len(ids));near(counts[c]['percent'],100*len(ids)/len(selected))
        near(summary['rule_counts' if c in EXCLUSION else 'diagnostic_rule_counts'][c],len(ids))
    near(counts['any_exclusion_rule']['n'],len(candidates));near(counts['remaining_if_applied']['n'],len(selected)-len(candidates))
    for overlap in summary['overlap']:
        ids=sorted(int(s['participant_id']) for s in summaries.values() if int(s['n_exclusion_rules'])==overlap['n_rules'])
        assert overlap['participant_ids']==ids and overlap['participant_n']==len(ids)
    all_s={**summaries,**hs};all_m={**metrics,**hm};all_b={**bins,**hb}
    pools=json.loads((out/'reference_pools.json').read_text());bands=read(out/'reference_bands.csv')
    assert set(pools)==set(raw)
    expected_band_keys=set()
    for rid,s in all_s.items():
        peers=[key for key,p in summaries.items() if p['participant_id']!=s['participant_id'] and p['anticipatory']=='clear' and int(p['n_not_assessable'])==0]
        assert pools[rid]==peers,(rid,pools[rid],peers)
    for row in bands:
        rid,scope,mid=row['run_id'],row['scope'],float(row['condition_trial_midpoint'])
        key=(rid,scope,mid);assert key not in expected_band_keys;expected_band_keys.add(key)
        near(row['peer_n'],len(pools[rid]))
        start=timeline(int(all_s[rid]['participant_id']))[scope][1]
        near(row['trial_midpoint'],mid+start-1)
        for field in ('accuracy','fast_fraction'):
            vals=[100*bins[p,scope,mid][field] for p in pools[rid] if bins[p,scope,mid][field] is not None]
            expected=np.percentile(vals,[25,50,75]) if vals else [None]*3
            for label,value in zip(('q25','median','q75'),expected):near(row[f'{field}_{label}'],value)
    assert expected_band_keys==set(all_b)
    matches=json.loads((out/'comparator_selection.json').read_text());expected_groups=defaultdict(list)
    for rid,s in summaries.items():
        if s['anticipatory']=='flag':expected_groups[s['main_block_order'],s['key_conflict'],s['key_nonconf']].append(int(s['participant_id']))
    assert len(matches)==len(expected_groups)
    for match in matches:
        key=match['main_block_order'],match['key_conflict'],match['key_nonconf']
        assert match['targets']==sorted(expected_groups[key])
        pool=[rid for rid,s in summaries.items() if (s['main_block_order'],s['key_conflict'],s['key_nonconf'])==key and s['anticipatory']=='clear' and int(s['n_not_assessable'])==0 and metrics[rid,'experimental_overall']['median_positive_rt_ms'] is not None]
        centers={};scales={}
        for f in ('median_positive_rt_ms','accuracy'):
            if pool:
                centers[f]=statistics.median(metrics[p,'experimental_overall'][f] for p in pool)
                scales[f]=statistics.median(abs(metrics[p,'experimental_overall'][f]-centers[f]) for p in pool)
        ranked=sorted([dict(participant_id=int(summaries[p]['participant_id']),score=sum(abs(metrics[p,'experimental_overall'][f]-centers[f])/scales[f] for f in centers if scales[f]>1e-12)) for p in pool],key=lambda r:(r['score'],r['participant_id']))
        assert match['ranked_candidates']==ranked and match['centers']==centers and match['median_absolute_deviations']==scales
        assert match['comparator']==(ranked[0]['participant_id'] if ranked else None)
    pairs=read(out/'historical_pair_metrics.csv')
    expected_pairs={(rid,scope) for rid,scope in hm if int(hs[rid]['participant_id']) in selected_ids}
    assert len(pairs)==len(expected_pairs) and {(p['historical_run_id'],p['scope']) for p in pairs}==expected_pairs
    for pair in pairs:
        old,selected_rid,scope=pair['historical_run_id'],pair['selected_run_id'],pair['scope']
        assert pair['replacement_identity_status']=='unconfirmed' and pair['historical_replacement_reason']=='not documented'
        assert selected_ids[int(pair['participant_id'])]==selected_rid
        for field in ('assessable','accuracy','n_timeouts','mean_answered_rt_ms','median_positive_rt_ms','n_fast','fast_fraction','fast_accuracy','target_difference_pp'):
            near(pair['historical_'+field],hm[old,scope][field]);near(pair['selected_'+field],metrics[selected_rid,scope][field])
    timing=read(out/'timing_diagnostics.csv')
    assert {(r['run_id'],int(r['block_idx']),int(r['trial_idx'])) for r in timing}=={(rid,int(r['block_idx']),int(r['trial_idx'])) for rid,rows in raw.items() for r in rows if timing_invalid(r)}
    links=Links();links.feed((out/'index.html').read_text())
    for link in links.paths:
        if link.startswith('#'):assert link[1:] in links.ids
        else:
            assert '://' not in link
            path=(out/unquote(link.split('#')[0])).resolve()
            assert path.is_relative_to(out) and path.is_file(),link
    plot_sources=json.loads((out/'plot_sources.json').read_text())
    assert {p['run_id'] for p in plot_sources['individuals']}==set(selected)
    assert {p['run_id'] for p in plot_sources['historical']}==set(historical)
    assert {(p['historical_run_id'],p['selected_run_id']) for p in plot_sources['historical_pairs']}=={(rid,selected_ids[int(rows[0]['participant_id'])]) for rid,rows in historical.items() if int(rows[0]['participant_id']) in selected_ids}
    for key in ('individuals','historical','comparison_pages','historical_pairs'):
        for p in plot_sources[key]:
            for suffix in ('.pdf','.png'):assert (out/(p['stem']+suffix)).is_file()
    artifacts=[out/r['path'] for r in manifest['outputs'] if Path(r['path']).suffix in ('.png','.pdf')]
    with ThreadPoolExecutor(max_workers=4) as executor:page_results=list(executor.map(check_artifact,artifacts))
    page_counts=dict(x for x in page_results if x)
    assert page_counts['all_individual_diagnostics.pdf']==len(selected)
    if historical:assert page_counts['historical_diagnostics.pdf']==len(historical)
    if plot_sources['historical_pairs']:assert page_counts['historical_comparisons.pdf']==len(plot_sources['historical_pairs'])
    if matches:assert page_counts['anticipatory_comparisons.pdf']==sum(math.ceil(len(m['targets'])/2) for m in matches)
    for name,pages in page_counts.items():
        if name not in ('all_individual_diagnostics.pdf','historical_diagnostics.pdf','historical_comparisons.pdf','anticipatory_comparisons.pdf'):assert pages==1,name
    if args.expect_current_cohort:
        assert len(selected)==48 and len(historical)==5 and sum(map(len,selected.values()))==86400
        assert sum(map(len,historical.values()))==9000
        assert candidates==[] and diagnostic==[3,5,12,16,42]
        assert sorted(int(s['participant_id']) for s in hs.values() if binary(s['exclude_by_rules']))==[5,17]
        assert not any(not m['assessable'] for m in all_m.values())
    print(json.dumps(dict(status='PASS',selected_runs=len(selected),historical_runs=len(historical),
        source_trials=sum(map(len,raw.values())),scope_metrics=len(all_m),bins=len(all_b),
        screening_results=len(checks)+len(hc),selected_candidates=candidates,diagnostic_only=diagnostic,
        png_count=sum(p.suffix=='.png' for p in artifacts),pdf_count=sum(p.suffix=='.pdf' for p in artifacts),
        independent_of_production_qc=True,visual_review_required=True),indent=2))


if __name__=='__main__':main()
