"""Boundary, provenance and design-contract tests for the audit."""
import ast
import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

from participant_qc import core
from participant_qc.run_qc import check_destination

ROOT = Path(__file__).resolve().parents[1]


def source_rows(pid=1, timestamp='20260101_120000'):
    rows = []
    order = ['CALIBRATION']+list(core.ORDERS[(pid-1) % 6])
    keys = ('D','J') if ((pid-1)//6) % 2 == 0 else ('J','D')
    for idx, code in enumerate(order, 1):
        for trial in range(1, (300 if idx == 1 else 500)+1):
            stimulus = 'conflict' if trial % 2 else 'nonconflict'
            response = stimulus if trial % 5 else ('nonconflict' if stimulus == 'conflict' else 'conflict')
            aided = code.startswith('AUTOMATION')
            rows.append(dict(participant_id=str(pid), run_timestamp=timestamp, block=code, block_idx=str(idx),
                trial_idx=str(trial), key_conflict=keys[0], key_nonconf=keys[1], stimulus=stimulus,
                response=response, correct=str(int(response == stimulus)),
                feedback='CORRECT' if response == stimulus else 'INCORRECT', rt_s='1', deadline_s='10',
                aid_label=('CONFLICT' if stimulus == 'conflict' else 'NON-CONF') if aided else '',
                aid_correct='1' if aided else '', aid_accuracy_setting={'AUTOMATION1': '.95', 'AUTOMATION2': '.65'}.get(code, '')))
    return rows


def write_rows(path, rows):
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with Path(path).open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(rows)


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.cfg = core.load_config(ROOT/'participant_qc/config.json')

    def load(self, rows, **kwargs):
        path = self.directory/'input.csv'
        write_rows(path, rows)
        return core.load_trials(path, **kwargs)

    def metric(self, **updates):
        m = {k: '' for k in core.META}
        m.update(scope='calibration_tail', scope_label='Calibration', n_trials=100,
                 accuracy=.8, target_difference_pp=0, n_fast=0, fast_fraction=0,
                 fast_accuracy=None, integrity_issues='', assessable=True)
        m.update(updates)
        return m

    def test_target_strict_boundaries(self):
        for acc, difference, status in [(.7,-10,'clear'),(.9,10,'clear'),(.699,-10.1,'flag'),(.901,10.1,'flag')]:
            m = self.metric(accuracy=acc, target_difference_pp=difference)
            self.assertEqual(core.screen(m, 'calibration_target', self.cfg)['status'], status)
        result = core.screen(self.metric(target_difference_pp=-20), 'manual_target', self.cfg)
        self.assertEqual(result['status'], 'flag')
        self.assertFalse(result['use_for_exclusion'])

    def test_joint_anticipatory_and_chance_boundaries(self):
        m = self.metric(n_fast=20, fast_fraction=.2, fast_accuracy=.55)
        self.assertEqual(core.screen(m, 'anticipatory', self.cfg)['status'], 'flag')
        for update in [dict(n_fast=19), dict(fast_fraction=.199), dict(fast_accuracy=.551), dict(fast_accuracy=None)]:
            self.assertEqual(core.screen({**m, **update}, 'anticipatory', self.cfg)['status'], 'clear')
        self.assertEqual(core.screen(self.metric(accuracy=.55), 'near_chance_or_worse', self.cfg)['status'], 'flag')
        self.assertEqual(core.screen(self.metric(accuracy=.5501), 'near_chance_or_worse', self.cfg)['status'], 'clear')
        self.assertEqual(core.screen({**m, 'assessable': False}, 'anticipatory', self.cfg)['status'], 'not_assessable')

    def test_fast_rt_timeout_denominators_and_empty(self):
        raw = source_rows()
        for idx, value in enumerate(['-.01','0','.199999','.2']): raw[idx]['rt_s'] = value
        raw[4].update(response='TIMEOUT', correct='', feedback='TOO SLOW', rt_s='.1')
        result = core.analyse(self.load(raw), self.cfg)
        m = next(m for m in result['metrics'] if m['scope'] == 'CALIBRATION')
        self.assertTrue(m['assessable'])
        self.assertEqual((m['n_fast'], m['n_nonpositive_rt'], m['n_timeouts_with_recorded_rt']), (3,2,1))
        self.assertEqual(m['fast_fraction'], 3/300)
        self.assertEqual(m['fast_accuracy'], 1)
        self.assertEqual(m['accuracy'], 240/300)
        self.assertEqual(m['answered_accuracy'], 240/299)
        manual = next(m for m in result['metrics'] if m['scope'] == 'MANUAL')
        self.assertIsNone(manual['fast_accuracy'])
        self.assertEqual(manual['n_fast'], 0)

    def test_allocation_all_twelve_cells_and_no_flags(self):
        for pid in range(1,13):
            result = core.analyse(self.load(source_rows(pid)), self.cfg)
            self.assertFalse(result['issues'])
            self.assertFalse(result['summaries'][0]['flagged_any_rule'])
            self.assertEqual(len(result['bins']), 36)
            self.assertEqual(len(result['checks']), 14)

    def test_contract_matches_current_task_without_importing_runtime(self):
        tree = ast.parse((ROOT/'python/atclab.py').read_text())
        assignment = next(n for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t,ast.Name) and t.id == 'BLOCKS' for t in n.targets))
        blocks = eval(compile(ast.Expression(assignment.value), '<task-blocks>', 'eval'), {'__builtins__': {}, 'dict': dict})
        self.assertEqual([(b['name'],b['N_TRIALS']) for b in blocks], [('CALIBRATION',300),('MANUAL',500),('AUTOMATION1',500),('AUTOMATION2',500)])
        self.assertEqual(blocks[0]['TARGET_ACC'], .8)
        self.assertEqual([b['AUTOMATION_ACC'] for b in blocks[2:]], [.95,.65])
        fn = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name == 'counterbalanced_block_ordering')
        ns = {}; exec(compile(ast.Module(body=[fn],type_ignores=[]), '<task-order>', 'exec'), ns)
        for pid in range(1,13): self.assertEqual(ns[fn.name](pid)[0], core.ORDERS[(pid-1)%6])

    def test_incomplete_and_invalid_scopes_not_clear(self):
        raw = source_rows(); del raw[301]
        result = core.analyse(self.load(raw), self.cfg)
        manual = next(m for m in result['metrics'] if m['scope'] == 'MANUAL')
        self.assertFalse(manual['assessable']); self.assertIsNone(manual['accuracy'])
        self.assertEqual(result['summaries'][0]['manual_target'], 'not_assessable')
        raw = source_rows(); raw[0]['key_conflict'] = 'J'; raw[300]['aid_label'] = 'CONFLICT'
        self.assertEqual(len(core.analyse(self.load(raw), self.cfg)['issues']), 3)
        for mutation in [dict(deadline_s='3'), dict(correct='0'), dict(rt_s='nan')]:
            raw = source_rows(); raw[0].update(mutation)
            self.assertTrue(core.analyse(self.load(raw), self.cfg)['issues'])

    def test_duplicate_missing_schema_and_multiple_runs_stop(self):
        raw = source_rows()
        with self.assertRaisesRegex(ValueError,'Duplicate'): self.load(raw+[raw[0]])
        with self.assertRaisesRegex(ValueError,'multiple runs'): self.load(raw+source_rows(timestamp='20260201_120000'))
        raw = source_rows(); [r.pop('deadline_s') for r in raw]
        with self.assertRaisesRegex(ValueError,'Missing required'): self.load(raw)

    def test_optional_new_timing_is_diagnostic(self):
        raw = source_rows()
        raw[0].update(rt_timing_version='ptb_queue_flip_v1', rt_backend_version='3.0.22.2',
                      stimulus_onset_s='100', response_timestamp_s='101', n_ignored_pre_onset_keydowns='0', response_readout_delay_s='.05')
        rows = next(iter(self.load(raw).values()))
        self.assertEqual(core.timing_issues(rows[0]), [])
        rows[0]['response_timestamp_s'] = '102'
        self.assertIn('Response timestamp and RT disagree', core.timing_issues(rows[0]))
        result = core.analyse({'test':rows}, self.cfg)
        self.assertFalse(result['issues'])
        self.assertFalse(result['summaries'][0]['exclude_by_rules'])
        rows[0].update(timeout=True, answered=False)
        self.assertIn('New-timing timeout contains response measurements', core.timing_issues(rows[0]))

    def test_repeated_ids_reconciled_without_selecting_by_mtime(self):
        current, earlier = source_rows(timestamp='20260201_120000'), source_rows()
        raw = self.directory/'raw'; raw.mkdir()
        write_rows(raw/'results_p001_new_b00_ALL.csv', current)
        write_rows(raw/'results_p001_old_b00_ALL.csv', earlier)
        people = self.load(current)
        historical, inventory = core.reconcile_raw(people,raw)
        self.assertEqual(len(historical),1)
        self.assertEqual(sum(r['selected_cohort'] for r in inventory),1)
        self.assertEqual({r['replacement_identity_status'] for r in inventory},{'unconfirmed'})
        self.assertEqual({r['relation_to_selected'] for r in inventory},{'selected','earlier'})
        earlier[0]['rt_s']='1.0000000000000'
        self.assertTrue(core.equivalent(earlier[0]['rt_s'],'1'))
        current[0]['rt_s']='1.2'; write_rows(raw/'results_p001_new_b00_ALL.csv',current)
        with self.assertRaisesRegex(ValueError,'Raw/collated mismatch'): core.reconcile_raw(people,raw)

    def test_candidate_union_and_comparator_constraints(self):
        result = core.analyse(self.load(source_rows()), self.cfg)
        first = result['summaries'][0]; base = next(m for m in result['metrics'] if m['scope']=='experimental_overall')
        summaries, metrics = [], []
        for pid, acc, rt in [(1,.7,700),(13,.8,1000),(25,.8,1000),(2,.8,1000),(37,.8,1000)]:
            s = {**first,'participant_id':pid,'run_id':f'p{pid}'}
            if pid == 1:s.update(anticipatory='flag',calibration_target='flag',exclude_by_rules=True,n_exclusion_rules=2)
            if pid == 2:s['main_block_order']='different'
            if pid == 37:s['key_conflict']='J'
            if pid == 13:s['manual_target']='flag'  # Other flags remain eligible.
            summaries.append(s);metrics.append({**base,'participant_id':pid,'accuracy':acc,'median_positive_rt_ms':rt})
        result.update(summaries=summaries,metrics=metrics)
        match = core.choose_comparators(result)[0]
        self.assertEqual(match['comparator'],13)
        self.assertEqual([r['participant_id'] for r in match['ranked_candidates']],[13,25])
        self.assertTrue(all(r['score']==0 for r in match['ranked_candidates']))
        summary=core.exclusion_summary(result)
        self.assertEqual(summary['unique_flagged_n'],1)
        self.assertEqual(summary['overlap'][1]['participant_ids'],[1])
        result['summaries']=[summaries[0]]
        self.assertIsNone(core.choose_comparators(result)[0]['comparator'])

    def test_peer_alignment_uses_selected_runs_and_condition(self):
        from participant_qc.plotting import peer_references
        source = source_rows(1)+source_rows(3)+source_rows(13)
        for r in source:
            if r['participant_id']=='3' and r['block']=='MANUAL':
                r.update(response='nonconflict' if r['stimulus']=='conflict' else 'conflict', correct='0', feedback='INCORRECT')
        selected = core.analyse(self.load(source),self.cfg)
        older = core.analyse(self.load(source_rows(1,'20251201_120000'),selected=False),self.cfg)
        combined = {k:selected[k]+older[k] for k in selected}
        _, _, pools, bands = peer_references(combined,selected)
        target = older['summaries'][0]['run_id']
        self.assertEqual(pools[target],['p003_20260101_120000','p013_20260101_120000'])
        row = next(b for b in bands if b['run_id']==target and b['scope']=='MANUAL')
        self.assertEqual([row['accuracy_'+k] for k in ('q25','median','q75')],[20,40,60])
        single = core.analyse(self.load(source_rows()),self.cfg)
        _, _, pools, bands = peer_references(single)
        self.assertEqual(list(pools.values()),[[]])
        self.assertTrue(all(b['accuracy_median'] is None for b in bands))

    def test_independent_validator_detects_metric_corruption(self):
        import importlib.util
        from participant_qc.reporting import write_csv
        spec = importlib.util.spec_from_file_location('qc_independent_validator',ROOT/'tests/validate_participant_qc.py')
        validator = importlib.util.module_from_spec(spec);spec.loader.exec_module(validator)
        raw = source_rows()
        people = self.load(raw);result=core.analyse(people,self.cfg)
        for filename,key in [('participant_summary','summaries'),('scope_metrics','metrics'),
                             ('screening_results','checks'),('trial_bin_summary','bins'),('integrity_issues','issues')]:
            write_csv(self.directory/(filename+'.csv'),result[key],['run_id','scope'])
        source = validator.group(raw)
        validator.validate_metrics(self.directory,source,self.cfg)
        result['metrics'][0]['accuracy']=.99
        write_csv(self.directory/'scope_metrics.csv',result['metrics'])
        with self.assertRaises(AssertionError):validator.validate_metrics(self.directory,source,self.cfg)

    def test_output_and_config_guards(self):
        with self.assertRaises(ValueError): check_destination(ROOT/'data/data_atc_all.csv',ROOT/'output',ROOT/'participant_qc/config.json',ROOT/'data/qc')
        dest=self.directory/'unowned';dest.mkdir();(dest/'keep.txt').write_text('unrelated')
        with self.assertRaises(ValueError): check_destination(ROOT/'data/data_atc_all.csv',ROOT/'output',ROOT/'participant_qc/config.json',dest)
        for k,value in [('bin_size',60),('chance_accuracy_max',float('nan')),('fast_count_min',True),('sensitivity_thresholds_ms',[200,100])]:
            cfg={**self.cfg,k:value};path=self.directory/'config.json';path.write_text(json.dumps(cfg))
            with self.assertRaises(ValueError):core.load_config(path)


if __name__ == '__main__':
    unittest.main()
