#!/usr/bin/env python3
"""Generate an isolated ATCLAB participant and historical-run audit."""
import argparse
import json
import os
import platform
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir())/'atclab_qc_matplotlib'))

from participant_qc.core import (META, CATEGORIES, analyse, choose_comparators, exclusion_summary,
                               load_config, load_trials, reconcile_raw, sha256, timing_issues)
from participant_qc.reporting import exclusion_table_rows, write_csv, write_json, write_report


def check_destination(source, raw_dir, config, destination):
    destination = destination.resolve()
    protected = [ROOT/p for p in ('data', 'output', 'plots', 'participant_qc', 'tests', 'python',
                                  'source_archives', '.git', '.agents', '.codex', 'validation', 'linear_models')]
    protected += [raw_dir.resolve()]
    if any(p.is_relative_to(destination) or destination.is_relative_to(p) for p in protected):
        raise ValueError('QC output must be separate from raw data, source, archives and existing analyses')
    if any(p.resolve().is_relative_to(destination) for p in (source, config)):
        raise ValueError('QC output cannot contain its inputs')
    if destination.exists():
        if not destination.is_dir():
            raise ValueError('Output must be a directory')
        if any(destination.iterdir()):
            receipt = destination/'manifest.json'
            if not receipt.exists() or json.loads(receipt.read_text()).get('generator') != 'atclab_participant_qc':
                raise ValueError('Refusing to replace a directory not owned by this audit')


def write_metrics(stage, result, prefix=''):
    for filename, key in [('scope_metrics', 'metrics'), ('screening_results', 'checks'),
                          ('trial_bin_summary', 'bins'), ('integrity_issues', 'issues')]:
        fields = (*META, 'scope', 'n_trials', 'n_expected', 'integrity_issues')
        write_csv(stage/f'{prefix}{filename}.csv', result[key], fields)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, default=ROOT/'data/data_atc_all.csv')
    parser.add_argument('--raw-dir', type=Path, default=ROOT/'output')
    parser.add_argument('--config', type=Path, default=Path(__file__).with_name('config.json'))
    parser.add_argument('--output-dir', type=Path, default=ROOT/'analysis_outputs/semester1_2026_qc')
    args = parser.parse_args(argv)
    source, raw_dir, config, destination = (p.resolve() for p in (args.input, args.raw_dir, args.config, args.output_dir))
    check_destination(source, raw_dir, config, destination)
    sources = sorted(Path(__file__).parent.glob('*.py'))+[config, ROOT/'python/atclab.py', ROOT/'collate_data.R']
    source_hashes = [dict(path=str(p.resolve()), sha256=sha256(p)) for p in sources]
    input_before = sha256(source)
    cfg = load_config(config)
    people = load_trials(source)
    historical, inventory = reconcile_raw(people, raw_dir)
    result, history = analyse(people, cfg), analyse(historical, cfg)
    comparisons = choose_comparators(result)
    summary = exclusion_summary(result)
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.'+destination.name+'.build-', dir=destination.parent))
    print(f'Building {len(people)} selected and {len(historical)} historical runs in {stage}', flush=True)
    write_csv(stage/'participant_summary.csv', result['summaries'])
    write_csv(stage/'historical_run_summary.csv', history['summaries'], result['summaries'][0])
    write_metrics(stage, result)
    write_metrics(stage, history, 'historical_')
    write_csv(stage/'run_inventory.csv', inventory)
    write_csv(stage/'exclusion_candidates.csv', [s for s in result['summaries'] if s['exclude_by_rules']], result['summaries'][0])
    write_csv(stage/'flagged_checks.csv', [c for c in result['checks'] if c['status'] == 'flag'], result['checks'][0])
    write_csv(stage/'exclusion_summary_table.csv', exclusion_table_rows(summary))
    write_json(stage/'exclusion_summary.json', summary)
    write_json(stage/'config_snapshot.json', cfg)
    write_json(stage/'comparator_selection.json', comparisons)
    timing = [dict(run_id=r['run_id'], participant_id=r['participant_id'], selected_cohort=r['selected_cohort'],
                   block_idx=r['block_idx'], trial_idx=r['trial_idx'], rt_timing_version=r.get('rt_timing_version', ''),
                   issues='; '.join(timing_issues(r))) for rows in list(people.values())+list(historical.values())
              for r in rows if timing_issues(r)]
    write_csv(stage/'timing_diagnostics.csv', timing,
              ('run_id','participant_id','selected_cohort','block_idx','trial_idx','rt_timing_version','issues'))
    selected_by_id = {s['participant_id']: s for s in result['summaries']}
    lookup = {(m['run_id'], m['scope']): m for m in result['metrics']}
    pairs = []
    for m in history['metrics']:
        selected = selected_by_id.get(m['participant_id'])
        if selected is None:
            continue
        other = lookup[selected['run_id'], m['scope']]
        row = dict(participant_id=m['participant_id'], historical_run_id=m['run_id'], selected_run_id=other['run_id'],
                   scope=m['scope'], replacement_identity_status='unconfirmed', historical_replacement_reason='not documented')
        for key in ('assessable','accuracy','n_timeouts','mean_answered_rt_ms','median_positive_rt_ms',
                    'n_fast','fast_fraction','fast_accuracy','target_difference_pp'):
            row['historical_'+key], row['selected_'+key] = m[key], other[key]
        pairs.append(row)
    write_csv(stage/'historical_pair_metrics.csv', pairs, ('participant_id','historical_run_id','selected_run_id','scope'))
    (stage/'exclusion_summary.txt').write_text(
        f"ATCLAB audit only: {summary['participant_n']} selected runs; {summary['unique_flagged_n']} exclusion candidates.\n"
        f"Candidate IDs: {summary['participant_ids']}. Remaining if applied: {summary['remaining_if_applied_n']}.\n"
        f"Diagnostic-only IDs: {summary['diagnostic_only_participant_ids']}.\n"
        f"Unassessable IDs: {summary['incomplete_assessment_ids']}.\n"
        f"Historical sessions: {len(historical)}; separate from cohort and reference pools.\n"
        "Historical replacement identities and reasons are unconfirmed. No exclusions applied; no trials trimmed.\n")
    from participant_qc.plotting import generate_plots
    plots = generate_plots(people, result, historical, history, cfg, comparisons, stage)
    write_json(stage/'reference_pools.json', plots.pop('pools'))
    write_csv(stage/'reference_bands.csv', plots.pop('bands'))
    write_json(stage/'plot_sources.json', dict(
        cohort_figures=['participant_summary.csv','scope_metrics.csv','screening_results.csv'],
        traces=['input CSV and inventoried raw files','trial_bin_summary.csv','historical_trial_bin_summary.csv',
                'reference_bands.csv','reference_pools.json'], **plots))
    write_report(stage, result, history, cfg, inventory, plots)
    if (sha256(source) != input_before or any(sha256(r['path']) != r['sha256'] for r in source_hashes+inventory)
            or {str(p.resolve()) for p in raw_dir.glob('results_*_b00_ALL.csv')} != {r['path'] for r in inventory}):
        raise RuntimeError(f'Inputs/source changed during generation; unpublished report retained in {stage}')
    import numpy, matplotlib
    manifest = dict(schema_version=1, generator='atclab_participant_qc', study='atclab_semester1_2026',
        created_utc=datetime.now(timezone.utc).isoformat(), input_csv=str(source), input_sha256=input_before,
        raw_dir=str(raw_dir), config_path=str(config), config_sha256=sha256(config), sources=source_hashes,
        raw_sources=[{k: r[k] for k in ('run_id','path','sha256','file_mtime_ns')} for r in inventory],
        participant_n=len(people), selected_run_n=len(people), historical_run_n=len(historical),
        selected_trial_n=sum(map(len, people.values())), historical_trial_n=sum(map(len, historical.values())),
        exclusions_applied=False, qc_data_filtered=False, unique_flagged_n=summary['unique_flagged_n'],
        integrity_scope_n=len(result['issues']), historical_integrity_scope_n=len(history['issues']),
        python_version=platform.python_version(), numpy_version=numpy.__version__, matplotlib_version=matplotlib.__version__,
        outputs=[dict(path=str(p.relative_to(stage)), bytes=p.stat().st_size, sha256=sha256(p))
                 for p in sorted(stage.rglob('*')) if p.is_file()])
    write_json(stage/'manifest.json', manifest)
    (stage/'COMPLETE.txt').write_text('Generation complete. Audit only; no exclusions applied. Independent validation is recorded separately.\n')
    if destination.exists():
        if any(destination.iterdir()):
            archive = destination.with_name(destination.name+'.previous_'+datetime.now().strftime('%Y%m%d_%H%M%S_%f'))
            destination.rename(archive)
        else:
            destination.rmdir()
    stage.rename(destination)
    print(json.dumps(dict(report=str(destination/'index.html'), selected_runs=len(people), historical_runs=len(historical),
                         exclusion_candidates=summary['participant_ids'], diagnostic_only=summary['diagnostic_only_participant_ids'],
                         integrity_scopes=len(result['issues']), historical_integrity_scopes=len(history['issues'])), indent=2))


if __name__ == '__main__':
    main()
