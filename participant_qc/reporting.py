"""Portable HTML report and auditable CSV/JSON exports."""
import csv
import html
import json
from pathlib import Path

from participant_qc.core import CATEGORIES, EXCLUSION_CATEGORIES, DIAGNOSTIC_CATEGORIES, exclusion_summary

LABELS = {'calibration_target': 'Calibration target', 'manual_target': 'Manual target (diagnostic)',
          'near_chance_or_worse': 'Near-chance or worse', 'anticipatory': 'Anticipatory responding'}


def write_csv(path, rows, empty_fields=()):
    fields = list(rows[0]) if rows else list(empty_fields)
    with Path(path).open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def exclusion_table_rows(summary):
    total = summary['participant_n']
    rows = []
    for c in EXCLUSION_CATEGORIES+DIAGNOSTIC_CATEGORIES:
        ids = summary['rule_participant_ids'][c]
        rows.append(dict(criterion=c, role='Candidate criterion' if c in EXCLUSION_CATEGORIES else 'Diagnostic only',
                         n=len(ids), percent=100*len(ids)/total if total else 0,
                         participant_ids='; '.join(f'{p:03d}' for p in ids)))
    rows.append(dict(criterion='any_exclusion_rule', role='Unique candidate total', n=summary['unique_flagged_n'],
                     percent=summary['unique_flagged_percent'],
                     participant_ids='; '.join(f'{p:03d}' for p in summary['participant_ids'])))
    rows.append(dict(criterion='remaining_if_applied', role='Hypothetical retained total', n=summary['remaining_if_applied_n'],
                     percent=100*summary['remaining_if_applied_n']/total if total else 0, participant_ids=''))
    return rows


def pct(value):
    return 'NA' if value is None else f'{100*value:.1f}%'


def interval(row, prefix):
    value = row[prefix]
    return 'NA' if value is None else f'{pct(value)} [{pct(row[prefix+"_lower"])}, {pct(row[prefix+"_upper"])}]'


def table(headers, rows):
    return '<div class="scroll"><table><thead><tr>'+''.join(f'<th>{html.escape(h)}</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join(f'<td>{v}</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'


def write_report(out, result, history, cfg, inventory, plots):
    out, esc = Path(out), html.escape
    summary = exclusion_summary(result)
    all_result = {k: result[k]+history[k] for k in result}
    pages = {p['run_id']: p for p in plots['individuals']+plots['historical']}
    headers = ['Recorded ID', 'Run timestamp']+[LABELS[c] for c in CATEGORIES]+['Candidate criteria met']

    def summary_rows(records):
        return [[f'<a href="#{s["run_id"]}">{s["participant_id"]:03d}</a>', esc(s['run_timestamp'])]
                +[f'<span class="{s[c]}">{s[c].replace("_", " ")}</span>' for c in CATEGORIES]
                +[str(s['n_exclusion_rules'])] for s in records]

    def detail(s):
        rid = s['run_id']; page = pages[rid]
        metrics = [m for m in all_result['metrics'] if m['run_id'] == rid]
        checks = [c for c in all_result['checks'] if c['run_id'] == rid and c['status'] != 'clear']
        reasons = ''.join(f'<li>{esc(LABELS[c["category"]])} / {esc(c["scope_label"])}: {esc(c["status"])}; {esc(c["rule"])} {esc(c["integrity_issues"])}</li>' for c in checks) or '<li>No flags on the configured screens.</li>'
        data = [[esc(m['scope_label']), f'{m["n_trials"]}/{m["n_expected"]}', interval(m, 'accuracy'),
                 pct(m['answered_accuracy']), str(m['n_timeouts']),
                 'NA' if m['mean_answered_rt_ms'] is None else f'{m["mean_answered_rt_ms"]:.1f}',
                 str(m['n_fast']), pct(m['fast_fraction']), interval(m, 'fast_accuracy'),
                 str(m['n_nonpositive_rt']), esc(m['integrity_issues']) or 'Complete'] for m in metrics]
        status = 'Selected cohort' if s['selected_cohort'] else 'Historical appendix; identity/replacement reason unconfirmed'
        timing = next(m for m in metrics if m['scope'] == 'experimental_overall')
        return f'''<details id="{rid}"><summary>Recorded ID {s['participant_id']:03d} · {s['run_timestamp']} · {status}</summary>
<p>Order: {esc(s['main_block_order'])}. Conflict key: {esc(s['key_conflict'])}; nonconflict key: {esc(s['key_nonconf'])}.</p>
<p><a href="{page['stem']}.pdf">Diagnostic PDF</a> | <a href="{page['stem']}.png">PNG</a></p><ul>{reasons}</ul>
{table(['Scope','Trials','Accuracy [Wilson interval]','Answered accuracy','Timeout n','Mean answered RT (ms)','Fast n','Fast proportion','Fast accuracy [Wilson interval]','Nonpositive n','Integrity'], data)}
<p>Experimental timing versions: {esc(timing['timing_versions'])}; {timing['n_timing_diagnostic_issues']} trials with timing diagnostic issues. Legacy RTs are preserved; newer timing metadata is not assigned retrospectively.</p></details>'''

    final_rows = [[esc(r['criterion']), esc(r['role']), str(r['n']), f'{r["percent"]:.1f}%', esc(r['participant_ids']) or 'None'] for r in exclusion_table_rows(summary)]
    figure_titles = {'screening_overview': 'Screening overview', 'calibration_manual_accuracy': 'Calibration and manual accuracy',
                     'whole_scope_accuracy': 'Whole-scope accuracy', 'anticipatory_cohort': 'Anticipatory cohort context'}
    figures = ''.join(f'<article><h3>{title}</h3><a href="{stem}.png"><img src="{stem}.png" alt="{title}" loading="lazy"></a><p><a href="{stem}.pdf">PDF</a> | <a href="{stem}.png">PNG</a></p></article>' for stem,title in figure_titles.items())
    pair_rows = [[esc(p['historical_run_id']), esc(p['selected_run_id']), f'<a href="{p["stem"]}.pdf">Paired PDF</a> | <a href="{p["stem"]}.png">PNG</a>', 'Unconfirmed'] for p in plots['historical_pairs']]
    historical_note = (f"{len(history['summaries'])} unselected sessions are audited separately. These are sessions, not an established count of distinct people. "
                       "The user recalls that later runs may have been replacement participants because originals performed poorly; no replacement log was found in the repository. "
                       "Screening results describe observed performance and do not establish historical reasons or participant identity.")
    raw_rows = [[esc(r['run_id']), str(r['selected_cohort']), esc(r['relation_to_selected']), str(r['n_trials']), esc(r['replacement_identity_status'])] for r in inventory]
    comparisons = ''.join(f'<li><a href="{p["stem"]}.pdf">Comparison for {", ".join(str(x) for x in p["targets"])}</a> (<a href="{p["stem"]}.png">PNG</a>); comparator {p["comparator"] if p["comparator"] is not None else "unavailable"}</li>' for p in plots['comparison_pages']) or '<li>No anticipatory flags in the selected cohort; no comparison pages required.</li>'
    exports = ['participant_summary.csv','scope_metrics.csv','screening_results.csv','flagged_checks.csv','integrity_issues.csv',
               'exclusion_candidates.csv','exclusion_summary_table.csv','exclusion_summary.json','exclusion_summary.txt',
               'trial_bin_summary.csv','run_inventory.csv','historical_run_summary.csv','historical_scope_metrics.csv',
               'historical_screening_results.csv','historical_trial_bin_summary.csv','historical_integrity_issues.csv',
               'historical_pair_metrics.csv','timing_diagnostics.csv','reference_pools.json','reference_bands.csv',
               'comparator_selection.json','plot_sources.json','config_snapshot.json','manifest.json']
    links = ' | '.join(f'<a href="{f}">{f}</a>' for f in exports)
    overlap = table(['Distinct criteria met','Unique candidates','IDs'], [[str(o['n_rules']),str(o['participant_n']),', '.join(f'{p:03d}' for p in o['participant_ids']) or 'None'] for o in summary['overlap']])
    text = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>ATCLAB participant and run audit</title><style>
body{{font:16px system-ui,sans-serif;max-width:1450px;margin:32px auto;padding:0 24px;color:#243746;background:#fafbfd}}h1,h2,h3{{color:#172b3a}}a{{color:#236b8e}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{padding:9px;border-bottom:1px solid #dfe5e9;text-align:left}}th{{background:#edf1f4}}.flag{{background:#fae6eb;color:#8c1735;font-weight:bold}}.not_assessable{{background:#fff0c4}}.clear{{color:#546773}}.scroll{{overflow:auto}}.figures{{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:24px}}article{{background:white;padding:18px;border:1px solid #dfe5e9}}img{{max-width:100%;height:auto}}details{{margin:14px 0;padding:12px;border:1px solid #dfe5e9;background:white}}summary{{cursor:pointer;font-weight:bold}}.notice{{background:#edf3f7;padding:16px;border-left:4px solid #236b8e}}input{{font:inherit;padding:7px}}
</style></head><body><h1>ATCLAB participant and run audit</h1>
<p>{len(result['summaries'])} selected runs; {len(history['summaries'])} additional historical sessions. <strong>No exclusions applied and no trials trimmed.</strong></p>
<div class="notice">The selected cohort follows the existing collated CSV. Historical session selection is separate from the retrospective screening rules. Manual accuracy deviation is diagnostic only.</div>
<h2>Selected-cohort exclusion summary</h2>
<p><strong>{summary['unique_flagged_n']} of {summary['participant_n']} ({summary['unique_flagged_percent']:.1f}%)</strong> meet at least one candidate criterion; {summary['remaining_if_applied_n']} would remain if applied. Candidates count once across scopes and criteria.</p>
{table(['Criterion','Role','Count','Percentage','IDs'], final_rows)}{overlap}
<p>{summary['diagnostic_only_n']} diagnostic-only cases; {len(summary['incomplete_assessment_ids'])} IDs with unassessable checks. Unassessable does not mean clear.</p>
<h2>Agreed retrospective screens</h2><ul>
<li>Calibration: final {cfg['calibration_tail_n']} trials; accuracy differs from 80% by more than {cfg['calibration_target_band_pp']:g} percentage points.</li>
<li>Near-chance or worse: all-trial accuracy ≤{100*cfg['chance_accuracy_max']:g}%.</li>
<li>Anticipatory: RT &lt;{1000*cfg['fast_rt_seconds']:g} ms on ≥{100*cfg['fast_fraction_min']:g}% of all trials, ≥{cfg['fast_count_min']} fast responses, and fast-response accuracy ≤{100*cfg['fast_accuracy_max']:g}%, jointly within one scope.</li>
<li>Diagnostic only: whole-manual accuracy differs from 80% by more than {cfg['manual_target_band_pp']:g} points.</li></ul>
<p>Whole scopes: full calibration (300), each experimental block (500), pooled automation (1,000), and all experimental trials (1,500). Calibration-tail screening is target-only. Timeouts are incorrect; fast accuracy uses answered fast trials. Exactly {1000*cfg['fast_rt_seconds']:g} ms is not fast; finite nonpositive answered RTs count as fast. Empty fast subsets have missing accuracy.</p>
<p>These are descriptive retrospective screens, not preregistered rules or evidence of equivalence to chance. {100*cfg['interval_level']:g}% Wilson intervals do not model serial dependence or adaptive calibration. Slow responding and manual/automation ordering do not add exclusion criteria. Timing anomalies are diagnostic only.</p>
<h2>Selected-cohort review table</h2><p><input id="search" aria-label="Search selected cohort" placeholder="Search ID, timestamp or status"></p><div id="cohort">{table(headers, summary_rows(result['summaries']))}</div>
<h2>Cohort figures</h2><div class="figures">{figures}</div>
<h2>Anticipatory comparisons</h2><ul>{comparisons}</ul>
<p>Comparators match block order and key mapping, are complete and pass the anticipatory screen; other flags do not disqualify them. Ranking uses median/MAD distance, with ID tie-breaks and no unmatched fallback. Peer bands use selected complete runs without anticipatory flags, excluding the focal recorded ID, aligned by condition and within-block trial across orders. They are descriptive and do not adjust for order effects.</p>
<h2>Historical-run appendix</h2><p>{historical_note}</p>
{table(headers, summary_rows(history['summaries']))}
{table(['Historical session','Selected session','Comparison','Replacement provenance'],pair_rows)}
{('<p><a href="historical_diagnostics.pdf">All historical diagnostics</a></p>' if plots['historical'] else '')}
{('<p><a href="historical_comparisons.pdf">All paired comparisons</a></p>' if plots['historical_pairs'] else '')}
<p>Historical sessions do not enter the main cohort totals or peer pools. An old session meeting a current screen does not establish why it was originally replaced.</p>
<h2>Run-selection inventory</h2><p>Selection is read from the existing collated file, not recalculated from timestamps. The collation script uses file modification times; the inventory records those separately from run timestamps. Additional later or unmatched raw runs are also reported rather than selected automatically.</p>
{table(['Run ID','Selected','Relation','Trial count','Identity status'],raw_rows)}
<h2>Individual diagnostics</h2><p><a href="all_individual_diagnostics.pdf">All selected-run diagnostics (PDF)</a></p>
{''.join(detail(s) for s in all_result['summaries'])}
<h2>Data and provenance</h2><p>{links}</p>
<script>
const search=document.getElementById('search');search.addEventListener('input',()=>document.querySelectorAll('#cohort tbody tr').forEach(row=>row.hidden=!row.textContent.toLowerCase().includes(search.value.toLowerCase())));
function openTarget(){{const t=document.getElementById(location.hash.slice(1));if(t&&t.tagName==='DETAILS')t.open=true;}}window.addEventListener('hashchange',openTarget);openTarget();
</script></body></html>'''
    (out/'index.html').write_text(text)
