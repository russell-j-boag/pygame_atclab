"""ATCLAB study contract, integrity checks and retrospective screening.

Adapted from the time-pressure audit. This module never filters study data.
The Semester 1 design is explicit: changing future task code cannot silently
reinterpret historical sessions. Task source is hashed and cross-checked in tests.
"""
import csv
import hashlib
import json
import math
import re
import statistics
from collections import defaultdict
from pathlib import Path

EPS = 1e-12
CONDITIONS = ['CALIBRATION', 'MANUAL', 'AUTOMATION1', 'AUTOMATION2']
LABELS = dict(zip(CONDITIONS, ['Calibration', 'Manual', 'Automation 95%', 'Automation 65%']))
ORDERS = [
    ('MANUAL', 'AUTOMATION1', 'AUTOMATION2'), ('MANUAL', 'AUTOMATION2', 'AUTOMATION1'),
    ('AUTOMATION1', 'MANUAL', 'AUTOMATION2'), ('AUTOMATION1', 'AUTOMATION2', 'MANUAL'),
    ('AUTOMATION2', 'MANUAL', 'AUTOMATION1'), ('AUTOMATION2', 'AUTOMATION1', 'MANUAL'),
]
SEGMENTS = [(c, LABELS[c]) for c in CONDITIONS]
SCOPES = SEGMENTS + [('aided_overall', 'Aided overall'), ('experimental_overall', 'Experimental overall')]
META = ('participant_id', 'run_timestamp', 'run_id', 'selected_cohort',
        'key_conflict', 'key_nonconf', 'main_block_order')
CATEGORIES = ['calibration_target', 'manual_target', 'near_chance_or_worse', 'anticipatory']
EXCLUSION_CATEGORIES = ['calibration_target', 'near_chance_or_worse', 'anticipatory']
DIAGNOSTIC_CATEGORIES = ['manual_target']
REQUIRED = {'participant_id', 'run_timestamp', 'block', 'block_idx', 'trial_idx',
            'key_conflict', 'key_nonconf', 'stimulus', 'response', 'correct', 'feedback',
            'rt_s', 'deadline_s', 'aid_label', 'aid_correct', 'aid_accuracy_setting'}
TIMING_FIELDS = ('rt_backend_version', 'stimulus_onset_s', 'response_timestamp_s',
                 'n_ignored_pre_onset_keydowns', 'response_readout_delay_s')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def empty(value):
    return value is None or str(value).strip().lower() in ('', 'na', 'nan')


def binary(value):
    return {'true': 1, 'false': 0, '1': 1, '0': 0}.get(str(value).strip().lower())


def load_config(path):
    cfg = json.loads(Path(path).read_text())
    default = json.loads(Path(__file__).with_name('config.json').read_text())
    if set(cfg) != set(default) or type(cfg['schema_version']) is not int or cfg['schema_version'] != 1:
        raise ValueError('Configuration must match the documented schema version 1')
    for k in ('calibration_tail_n', 'fast_count_min', 'bin_size'):
        if type(cfg[k]) is not int or cfg[k] <= 0:
            raise ValueError(f'{k} must be a positive integer')
    if cfg['calibration_tail_n'] > 250 or any(n % cfg['bin_size'] for n in (300, 500)):
        raise ValueError('Calibration tail must be post-burn-in; bins must divide both block lengths')
    for k in ('chance_accuracy_max', 'fast_fraction_min', 'fast_accuracy_max', 'interval_level',
              'fast_rt_seconds', 'calibration_target_band_pp', 'manual_target_band_pp'):
        limit = 10 if k == 'fast_rt_seconds' else 100 if k.endswith('_pp') else 1
        if type(cfg[k]) not in (int, float) or not math.isfinite(cfg[k]) or not 0 < cfg[k] < limit:
            raise ValueError(f'Invalid {k}')
    thresholds = cfg['sensitivity_thresholds_ms']
    if (not isinstance(thresholds, list) or not thresholds
            or any(type(x) is not int or x <= 0 for x in thresholds)
            or thresholds != sorted(set(thresholds))):
        raise ValueError('Sensitivity thresholds must be positive, unique, sorted integer milliseconds')
    return cfg


def wilson(k, n, level=.95):
    if not n:
        return None, None
    z = statistics.NormalDist().inv_cdf((1+level)/2)
    scale = 1+z*z/n
    center = (k/n+z*z/(2*n))/scale
    half = z*math.sqrt((k/n)*(1-k/n)/n+z*z/(4*n*n))/scale
    return max(0, center-half), min(1, center+half)


def segments_for_person(rows):
    order = ('CALIBRATION',) + ORDERS[(rows[0]['participant_id']-1) % 6]
    segments, lo = [], 1
    for idx, code in enumerate(order, 1):
        n = 300 if idx == 1 else 500
        block = dict(AUTOMATION_ON=code.startswith('AUTOMATION'),
                     AID_ACCURACY={'AUTOMATION1': .95, 'AUTOMATION2': .65}.get(code),
                     TRIAL_DEADLINE_MS=10000)
        segments.append((code, LABELS[code], lo, lo+n-1, idx, block))
        lo += n
    return segments


def scopes_for_person(rows, cfg):
    segments = segments_for_person(rows)
    scopes = [(c, LABELS[c], set(range(lo, hi+1))) for c in CONDITIONS
              for code, _, lo, hi, *_ in segments if c == code]
    scopes += [
        ('aided_overall', 'Aided overall', {t for c, _, lo, hi, *_ in segments
                                          if c.startswith('AUTOMATION') for t in range(lo, hi+1)}),
        ('experimental_overall', 'Experimental overall', set(range(301, 1801))),
        ('calibration_tail', f"Calibration final {cfg['calibration_tail_n']} trials",
         set(range(301-cfg['calibration_tail_n'], 301))),
    ]
    return scopes


def load_trials(path, *, selected=True, allow_multiple=False):
    people, keys = defaultdict(list), set()
    with Path(path).open(newline='') as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED - set(reader.fieldnames or [])
        if missing:
            raise ValueError('Missing required trial columns: ' + ', '.join(sorted(missing)))
        for line, raw in enumerate(reader, 2):
            row = dict(raw)
            # Keep source values for numeric-aware reconciliation; never rewrite exports.
            row['_raw'] = dict(raw)
            for k in ('participant_id', 'block_idx', 'trial_idx'):
                value = number(row[k])
                if value is None or value <= 0 or value % 1:
                    raise ValueError(f'Invalid {k} at CSV line {line}')
                row[k] = int(value)
            if not re.fullmatch(r'\d{8}_\d{6}', row['run_timestamp']):
                raise ValueError(f'Invalid run timestamp at CSV line {line}')
            pid = row['participant_id']
            rid = f"p{pid:03d}_{row['run_timestamp']}"
            key = (rid, row['block_idx'], row['trial_idx'])
            if key in keys:
                raise ValueError(f'Duplicate trial identity at CSV line {line}')
            keys.add(key)
            row.update(run_id=rid, selected_cohort=selected,
                       main_block_order='|'.join(ORDERS[(pid-1) % 6]),
                       global_trial=(0 if row['block_idx'] == 1 else 300+500*(row['block_idx']-2))+row['trial_idx'],
                       rt=number(row['rt_s']), answered=row['response'] in ('conflict', 'nonconflict'),
                       timeout=row['response'] == 'TIMEOUT')
            row['is_correct'] = int(row['answered'] and row['response'] == row['stimulus'])
            people[rid].append(row)
    if not people:
        raise ValueError('No trial records')
    seen = set()
    for rid, rows in people.items():
        pid = rows[0]['participant_id']
        if pid in seen and not allow_multiple:
            raise ValueError(f'Ambiguous multiple runs for participant {pid}; select one run explicitly')
        seen.add(pid)
        rows.sort(key=lambda r: (r['block_idx'], r['trial_idx']))
    return dict(sorted(people.items()))


def timing_issues(row):
    """Version-aware diagnostic evidence, never a fourth exclusion rule."""
    version = row.get('rt_timing_version')
    if empty(version):
        return []
    if version != 'ptb_queue_flip_v1':
        return ['Unrecognised timing version']
    issues = []
    onset, stamp = number(row.get('stimulus_onset_s')), number(row.get('response_timestamp_s'))
    ignored = number(row.get('n_ignored_pre_onset_keydowns'))
    if empty(row.get('rt_backend_version')) or onset is None or ignored is None or ignored < 0 or ignored % 1:
        issues.append('Missing or invalid timing metadata')
    if row['answered']:
        delay = number(row.get('response_readout_delay_s'))
        if (onset is None or stamp is None or row['rt'] is None or stamp < onset
                or not math.isclose(stamp-onset, row['rt'], rel_tol=1e-9, abs_tol=1e-8)):
            issues.append('Response timestamp and RT disagree')
        if delay is None or delay < 0:
            issues.append('Missing or negative response readout delay')
        if row['rt'] is not None and number(row['deadline_s']) is not None and row['rt'] >= number(row['deadline_s']):
            issues.append('New-timing response at or beyond deadline')
    elif row['timeout'] and any(not empty(row.get(k)) for k in ('rt_s', 'response_timestamp_s', 'response_readout_delay_s')):
        issues.append('New-timing timeout contains response measurements')
    return issues


def validate_person(rows):
    pid = rows[0]['participant_id']
    mapping = ('D', 'J') if ((pid-1)//6) % 2 == 0 else ('J', 'D')
    segments = {s[4]: s for s in segments_for_person(rows)}
    errors, global_errors = defaultdict(list), []
    for r in rows:
        t = r['global_trial']
        segment = segments.get(r['block_idx'])
        if segment is None or not 1 <= r['trial_idx'] <= (300 if r['block_idx'] == 1 else 500):
            global_errors.append('Trial outside expected block/trial bounds')
            continue
        code, _, lo, hi, idx, block = segment
        if r['block'] != code:
            errors[t].append('Block sequence mismatch')
        if (r['key_conflict'], r['key_nonconf']) != mapping:
            errors[t].append('Key mapping mismatch')
        if number(r['deadline_s']) != 10:
            errors[t].append('Deadline differs from the Semester 1 study contract (10 seconds)')
        if r['stimulus'] not in ('conflict', 'nonconflict') or not (r['answered'] or r['timeout']):
            errors[t].append('Invalid stimulus or response')
        if r['answered'] and (binary(r['correct']) != r['is_correct'] or r['feedback'] != ('CORRECT' if r['is_correct'] else 'INCORRECT')):
            errors[t].append('Response correctness/feedback mismatch')
        if r['timeout'] and ((not empty(r['correct']) and binary(r['correct']) != 0) or r['feedback'] != 'TOO SLOW'):
            errors[t].append('Timeout correctness/feedback mismatch')
        if r['answered'] and r['rt'] is None:
            errors[t].append('Answered trial has missing/nonfinite RT')
        if r['timeout'] and not empty(r['rt_s']) and r['rt'] is None:
            errors[t].append('Timeout has invalid RT')
        if block['AUTOMATION_ON']:
            advice = {'CONFLICT': 'conflict', 'NON-CONF': 'nonconflict'}.get(r['aid_label'])
            if (advice is None or binary(r['aid_correct']) != int(advice == r['stimulus'])
                    or number(r['aid_accuracy_setting']) != block['AID_ACCURACY']):
                errors[t].append('Advice label, correctness or reliability mismatch')
        elif any(not empty(r[k]) for k in ('aid_label', 'aid_correct', 'aid_accuracy_setting')):
            errors[t].append('Unexpected advice outside automation')
        if not empty(r.get('is_PM')) and binary(r['is_PM']) != 0:
            errors[t].append('PM trial outside the supported study design')
        if not empty(r.get('flash_onsets')):
            errors[t].append('DRT events outside the supported study design')
    return errors, sorted(set(global_errors))


def scope_metrics(rows, scope, label, lo, hi, cfg, errors, global_errors, expected_trials=None):
    first = rows[0]
    expected_trials = set(range(lo, hi+1)) if expected_trials is None else expected_trials
    selected = [r for r in rows if r["global_trial"] in expected_trials]
    issues = set(global_errors)
    if {r["global_trial"] for r in selected} != expected_trials:
        issues.add(f"Incomplete scope: expected {len(expected_trials)} trials, found {len(selected)}")
    for r in selected:
        issues.update(errors.get(r["global_trial"], []))
    assessable = not issues
    fast = [r for r in selected if r["answered"] and r["rt"] is not None and r["rt"] < cfg["fast_rt_seconds"]]
    k, fk = sum(r["is_correct"] for r in selected), sum(r["is_correct"] for r in fast)
    n, nf = len(selected), len(fast)
    lower, upper = wilson(k, n, cfg["interval_level"]) if assessable else (None, None)
    fl, fu = wilson(fk, nf, cfg["interval_level"]) if assessable else (None, None)
    positive = [r["rt"] for r in selected if r["answered"] and r["rt"] is not None and r["rt"] > 0]
    m = {k: first[k] for k in META}
    m.update(calibration_target_accuracy=0.80,
        scope=scope, scope_label=label, trial_start=lo, trial_end=hi,
        assessable=assessable, integrity_issues="; ".join(sorted(issues)), n_expected=len(expected_trials),
        n_trials=n, n_answered=sum(r["answered"] for r in selected), n_timeouts=sum(r["timeout"] for r in selected),
        n_correct=k if assessable else None, accuracy=k/n if assessable else None,
        accuracy_lower=lower, accuracy_upper=upper, n_fast=nf,
        fast_fraction=nf/n if assessable else None, n_fast_correct=fk if assessable else None,
        fast_accuracy=fk/nf if assessable and nf else None, fast_accuracy_lower=fl, fast_accuracy_upper=fu,
        n_nonpositive_rt=sum(r["answered"] and r["rt"] is not None and r["rt"] <= 0 for r in selected),
        n_positive_fast=sum(r["rt"] > 0 for r in fast),
        median_positive_rt_ms=1000*statistics.median(positive) if positive else None)
    answered_n = sum(r["answered"] for r in selected)
    m["answered_accuracy"] = k/answered_n if assessable and answered_n else None
    m["timeout_fraction"] = m["n_timeouts"]/n if assessable else None
    m["n_timeouts_with_recorded_rt"] = sum(r["timeout"] and r["rt"] is not None for r in selected)
    m["n_beyond_deadline"] = sum(r["answered"] and r["rt"] is not None
        and number(r["deadline_s"]) is not None and r["rt"] > number(r["deadline_s"]) for r in selected)
    m["mean_answered_rt_ms"] = 1000*statistics.mean(r["rt"] for r in selected if r["answered"] and r["rt"] is not None) if any(r["answered"] and r["rt"] is not None for r in selected) else None
    m["timing_versions"] = "|".join(sorted({"legacy_unspecified" if empty(r.get("rt_timing_version")) else r["rt_timing_version"] for r in selected}))
    m["n_legacy_timing"] = sum(empty(r.get("rt_timing_version")) for r in selected)
    m["n_timing_diagnostic_issues"] = sum(bool(timing_issues(r)) for r in selected)
    for ms in cfg["sensitivity_thresholds_ms"]:
        m[f"fraction_rt_lt_{ms}ms"] = sum(r["answered"] and r["rt"] is not None and r["rt"] < ms/1000 for r in selected)/n if assessable else None
    m["target_difference_pp"] = 100*(m["accuracy"]-m["calibration_target_accuracy"]) if assessable else None
    return m


def screen(m, category, cfg):
    if category not in CATEGORIES:
        raise ValueError(f"Unknown screening category: {category}")
    a, f, fa = m["accuracy"], m["fast_fraction"], m["fast_accuracy"]
    if category in ("calibration_target", "manual_target"):
        band = cfg[f"{category}_band_pp"]
        rule = f"Absolute target difference > {band:g} pp"
        flagged = a is not None and abs(m["target_difference_pp"]) > band+EPS
    elif category == "near_chance_or_worse":
        rule = f"All-trial accuracy <= {100*cfg['chance_accuracy_max']:g}%"
        flagged = a is not None and a <= cfg["chance_accuracy_max"]+EPS
    else:
        rule = (f"RT < {1000*cfg['fast_rt_seconds']:g} ms; fraction >= {cfg['fast_fraction_min']:g}; "
                f"n >= {cfg['fast_count_min']}; fast accuracy <= {cfg['fast_accuracy_max']:g}")
        flagged = (f is not None and fa is not None and f >= cfg["fast_fraction_min"]-EPS
                   and m["n_fast"] >= cfg["fast_count_min"] and fa <= cfg["fast_accuracy_max"]+EPS)
    return {**{k: m[k] for k in (*META, "scope", "scope_label",
        "n_trials", "accuracy", "target_difference_pp", "n_fast", "fast_fraction", "fast_accuracy", "integrity_issues")},
        "category": category, "use_for_exclusion": category in EXCLUSION_CATEGORIES, "rule": rule,
        "status": "not_assessable" if not m["assessable"] else "flag" if flagged else "clear"}


def analyse(people, cfg):
    metrics, checks, summaries, bins, issues = [], [], [], [], []
    for pid, rows in people.items():
        errors, global_errors = validate_person(rows)
        person_metrics, person_checks = [], []
        scopes = scopes_for_person(rows, cfg)
        for scope, label, expected in scopes:
            m = scope_metrics(rows, scope, label, min(expected), max(expected), cfg, errors, global_errors, expected)
            person_metrics.append(m)
            categories = ["calibration_target"] if scope == "calibration_tail" else ["near_chance_or_worse", "anticipatory"]
            if scope == "MANUAL":
                categories += ["manual_target"]
            person_checks.extend(screen(m, category, cfg) for category in categories)
            if not m["assessable"]:
                issues.append({k: m[k] for k in (*META, "scope", "n_trials", "n_expected", "integrity_issues")})
        for s in segments_for_person(rows):
            for lo in range(s[2], s[3]+1, cfg["bin_size"]):
                b = scope_metrics(rows, s[0], s[1], lo, lo+cfg["bin_size"]-1, cfg, errors, global_errors)
                b["trial_midpoint"] = lo+(cfg["bin_size"]-1)/2
                b["condition_trial_start"] = lo-s[2]+1
                b["condition_trial_midpoint"] = b["trial_midpoint"]-s[2]+1
                bins.append(b)
        summary = {k: rows[0][k] for k in META}
        for category in CATEGORIES:
            statuses = [c["status"] for c in person_checks if c["category"] == category]
            summary[category] = "flag" if "flag" in statuses else "not_assessable" if "not_assessable" in statuses else "clear"
        flagged = [c for c in person_checks if c["status"] == "flag"]
        summary.update(n_flags=len(flagged), n_not_assessable=sum(c["status"] == "not_assessable" for c in person_checks),
                       n_flagged_rules=sum(summary[c] == "flag" for c in CATEGORIES),
                       flagged_any_rule=bool(flagged),
                       n_exclusion_rules=sum(summary[c] == "flag" for c in EXCLUSION_CATEGORIES),
                       exclude_by_rules=any(summary[c] == "flag" for c in EXCLUSION_CATEGORIES),
                       exclusion_reasons="; ".join(f"{c['category']}:{c['scope']}" for c in flagged if c["use_for_exclusion"]),
                       review_required=bool(flagged) or any(not m["assessable"] for m in person_metrics),
                       reasons="; ".join(f"{c['category']}:{c['scope']}" for c in flagged))
        summaries.append(summary); metrics.extend(person_metrics); checks.extend(person_checks)
    return dict(metrics=metrics, checks=checks, summaries=summaries, bins=bins, issues=issues)


def exclusion_summary(result):
    summaries = result['summaries']
    candidates = [s for s in summaries if s['exclude_by_rules']]
    diagnostic = [s['participant_id'] for s in summaries if s['flagged_any_rule'] and not s['exclude_by_rules']]
    n = len(summaries)
    return dict(participant_n=n, unique_flagged_n=len(candidates),
        unique_flagged_percent=100*len(candidates)/n if n else 0,
        remaining_if_applied_n=n-len(candidates), participant_ids=[s['participant_id'] for s in candidates],
        exclusion_categories=EXCLUSION_CATEGORIES, diagnostic_categories=DIAGNOSTIC_CATEGORIES,
        rule_counts={c: sum(s[c] == 'flag' for s in summaries) for c in EXCLUSION_CATEGORIES},
        diagnostic_rule_counts={c: sum(s[c] == 'flag' for s in summaries) for c in DIAGNOSTIC_CATEGORIES},
        rule_participant_ids={c: [s['participant_id'] for s in summaries if s[c] == 'flag'] for c in CATEGORIES},
        diagnostic_only_participant_ids=diagnostic, diagnostic_only_n=len(diagnostic),
        overlap=[dict(n_rules=k, participant_n=sum(s['n_exclusion_rules'] == k for s in candidates),
                      participant_ids=[s['participant_id'] for s in candidates if s['n_exclusion_rules'] == k])
                 for k in range(1, 4)],
        incomplete_assessment_ids=[s['participant_id'] for s in summaries if s['n_not_assessable']],
        exclusions_applied=False, qc_data_filtered=False,
        note='Selected cohort only. Candidates are a union across three criteria; manual target deviation is diagnostic only. Earlier runs are separate and identity/replacement reasons remain unconfirmed.')


def choose_comparators(result):
    summaries = result['summaries']
    overall = {m['participant_id']: m for m in result['metrics'] if m['scope'] == 'experimental_overall'}
    matches = defaultdict(list)
    for s in summaries:
        if s['anticipatory'] == 'flag':
            matches[s['main_block_order'], s['key_conflict'], s['key_nonconf']].append(s['participant_id'])
    output = []
    for match, targets in sorted(matches.items()):
        pool = [s['participant_id'] for s in summaries
                if (s['main_block_order'], s['key_conflict'], s['key_nonconf']) == match
                and s['anticipatory'] == 'clear' and s['n_not_assessable'] == 0
                and overall[s['participant_id']]['median_positive_rt_ms'] is not None]
        centers, scales = {}, {}
        for key in ('median_positive_rt_ms', 'accuracy'):
            if pool:
                centers[key] = statistics.median(overall[p][key] for p in pool)
                scales[key] = statistics.median(abs(overall[p][key]-centers[key]) for p in pool)
        ranked = sorted([dict(participant_id=p, score=sum(abs(overall[p][k]-centers[k])/scales[k]
                            for k in centers if scales[k] > EPS)) for p in pool],
                        key=lambda r: (r['score'], r['participant_id']))
        output.append(dict(main_block_order=match[0], key_conflict=match[1], key_nonconf=match[2],
            targets=sorted(targets), comparator=ranked[0]['participant_id'] if ranked else None,
            ranked_candidates=ranked, centers=centers, median_absolute_deviations=scales,
            note='Zero-MAD metrics contribute zero; ties use participant ID.' if ranked else 'No complete matching comparator available.'))
    return output


def equivalent(a, b):
    if a == b or empty(a) and empty(b):
        return True
    x, y = number(a), number(b)
    return x is not None and y is not None and math.isclose(x, y, rel_tol=1e-12, abs_tol=1e-12)


def reconcile_raw(people, directory):
    """Inventory every combined export; selected identities come only from input CSV."""
    raw_runs, paths, raw_hashes = {}, {}, {}
    for path in sorted(Path(directory).glob('results_*_b00_ALL.csv')):
        before = sha256(path)
        runs = load_trials(path, selected=False)
        if sha256(path) != before:
            raise RuntimeError(f'Raw export changed during read: {path}')
        if len(runs) != 1:
            raise ValueError(f'Combined export must contain one run: {path}')
        rid, rows = next(iter(runs.items()))
        if rid in raw_runs:
            raise ValueError(f'Ambiguous duplicate raw export for {rid}')
        raw_runs[rid], paths[rid], raw_hashes[rid] = rows, path.resolve(), before
    inventory, historical = [], {}
    for rid, rows in people.items():
        if rid not in raw_runs:
            raise ValueError(f'No raw export matching selected run {rid}')
        raw = raw_runs[rid]
        if len(rows) != len(raw):
            raise ValueError(f'Raw/collated row-count mismatch for {rid}')
        for a, b in zip(rows, raw):
            for k in set(a['_raw']) | set(b['_raw']):
                if not equivalent(a['_raw'].get(k), b['_raw'].get(k)):
                    raise ValueError(f'Raw/collated mismatch for {rid} trial {a["trial_idx"]}, column {k}')
    for rid, rows in raw_runs.items():
        pid = rows[0]['participant_id']
        selected = rid in people
        if not selected:
            historical[rid] = rows
        selected_rid = next((k for k, v in people.items() if v[0]['participant_id'] == pid), '')
        stamp = rows[0]['run_timestamp']
        relation = ('selected' if selected else 'earlier' if selected_rid and stamp < people[selected_rid][0]['run_timestamp']
                    else 'later' if selected_rid else 'no_selected_run')
        inventory.append(dict(participant_id=pid, run_timestamp=stamp, run_id=rid,
            selected_cohort=selected, relation_to_selected=relation, selected_run_id=selected_rid,
            n_trials=len(rows), path=str(paths[rid]), sha256=raw_hashes[rid],
            file_mtime_ns=paths[rid].stat().st_mtime_ns,
            replacement_identity_status='unconfirmed' if sum(r[0]['participant_id'] == pid for r in raw_runs.values()) > 1 else 'no_repeated_id',
            selection_basis='Existing collated CSV identity; collation uses file modification time',
            historical_replacement_reason='not documented'))
    return historical, inventory
