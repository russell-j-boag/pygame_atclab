"""Timestamp invariants and task integration; no native input or study writes."""

from contextlib import contextmanager, ExitStack
import csv
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
import numpy as np
import pygame
import response_timing as rt
import atclab as task

KEYMAP = {"D": "conflict", "J": "nonconflict"}


def event(key, time, pressed=True, lag=.05):
    return rt.KeyEvent(key, pressed, time, time + lag)


def window(held=(), duration=5.0):
    w = rt.ResponseWindow(99, held, KEYMAP, rt.PTB_VERSION)
    w.mark_onset(100, duration)
    return w


def write_rows(path, rows):
    with Path(path).open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


class TimestampTests(unittest.TestCase):
    def test_original_failure_early_press_is_not_relabelled_as_positive_rt(self):
        w = window()
        w.consume([event("D", 99.990), event("D", 99.995, False), event("J", 100.0005)])
        self.assertEqual(w.response, "nonconflict")
        self.assertAlmostEqual(w.result()["rt_s"], .0005, places=12)
        self.assertEqual(w.result()["n_ignored_pre_onset_keydowns"], 1)

    def test_held_key_must_be_released_other_key_is_available(self):
        w = window(held={"D"})
        w.consume([event("D", 100.1), event("J", 100.2)])
        self.assertEqual(w.response, "nonconflict")
        w = window(held={"D"})
        w.consume([event("D", 100.1), event("D", 100.2, False), event("D", 100.3)])
        self.assertAlmostEqual(w.result()["rt_s"], .3)

    def test_early_press_held_across_onset_requires_release(self):
        w = window()
        w.consume([event("D", 99.9), event("D", 100.1)])
        self.assertIsNone(w.response)
        w.consume([event("D", 100.2, False), event("D", 100.25)])
        self.assertAlmostEqual(w.result()["rt_s"], .25)

    def test_first_press_by_time_and_stable_equal_time_tie(self):
        w = window()
        w.consume([event("J", 100.2), event("D", 100.1)])
        self.assertEqual(w.response, "conflict")
        w = window()
        w.consume([event("J", 100.1), event("D", 100.1)])
        self.assertEqual(w.response, "nonconflict")
        w.expire(110)
        self.assertEqual(w.response, "nonconflict")

    def test_no_floor_and_half_millisecond_difference_survives_csv(self):
        results = []
        for delta in (.000001, .150123456789, .150623456789):
            w = window()
            w.consume([event("D", 100 + delta)])
            results.append(w.result())
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "trial.csv"
            write_rows(path, results)
            with path.open() as f:
                restored = list(csv.DictReader(f))
        for before, after in zip(results, restored):
            self.assertEqual(before["rt_s"], float(after["rt_s"]))
            self.assertEqual(before["response_timestamp_s"], float(after["response_timestamp_s"]))
        self.assertAlmostEqual(float(restored[2]["rt_s"]) - float(restored[1]["rt_s"]), .0005, places=12)

    def test_rendering_delays_do_not_change_rt(self):
        for lag in (.008, .020, .050):
            with self.subTest(lag=lag):
                w = window()
                w.consume([event("D", 100.1234567, lag=lag)])
                self.assertAlmostEqual(w.result()["rt_s"], .1234567, places=12)
                self.assertAlmostEqual(w.result()["response_readout_delay_s"], lag, places=12)

    def test_deadline_uses_event_time_not_processing_time(self):
        for delta, expected in ((4.999999, "conflict"), (5., "TIMEOUT"), (5.000001, "TIMEOUT")):
            w = window()
            w.consume([event("D", 100 + delta, lag=.05)])
            w.expire(105.1)
            self.assertEqual(w.response, expected)
            if expected == "TIMEOUT":
                self.assertIsNone(w.result()["rt_s"])
                self.assertIsNone(w.result()["response_timestamp_s"])
                self.assertIsNone(w.result()["response_readout_delay_s"])

    def test_onset_exactly_is_eligible_and_no_deadline_works(self):
        w = window(duration=None)
        w.expire(10000)
        self.assertIsNone(w.response)
        w.consume([event("D", 100)])
        self.assertEqual(w.result()["rt_s"], 0)

    def test_invalid_clock_or_event_order_fails(self):
        for e in (event("D", float("nan")), rt.KeyEvent("D", True, 101, 100)):
            with self.assertRaises(rt.TimingError):
                window().consume([e])
        w = window()
        w.consume([event("D", 99.9)])
        with self.assertRaises(rt.TimingError):
            w.consume([event("D", 99.8)])


class NativeAdapterContractTests(unittest.TestCase):
    def test_documented_native_key_codes_and_all_key_events(self):
        # Independent values from PTB KbName.m, not pygame key constants.
        expected = {'darwin': {'D':7, 'J':13, '9':38, 'KP9':97, 'SPACE':44},
                    'win32': {'D':68, 'J':74, '9':57, 'KP9':105, 'SPACE':32}}
        self.assertEqual(rt.KEY_CODES, expected)
        for platform, codes in expected.items():
            ptb, _ = self.fake_ptb()
            with self.context(ptb, platform), rt.PsychtoolboxKeyboard(keys=codes) as backend:
                with backend.trial({'D':'conflict','J':'nonconflict','9':'pm','KP9':'pm'}):
                    for name, code in codes.items():
                        ptb.pending.append(dict(Keycode=code, Pressed=1, Time=100.075))
                        events=backend.drain()
                        self.assertEqual([(e.key,e.timestamp_s) for e in events],[(name,100.075)])

    def test_nonempty_held_snapshot_and_snapshot_event_ignored(self):
        ptb, _ = self.fake_ptb()
        original = ptb.PsychHID
        def hid(name,*args):
            if name=='KbCheck':
                state=np.zeros((1,256)); state[0,6]=1; state[0,96]=1
                return 1,100.,state
            return original(name,*args)
        ptb.PsychHID=hid
        with self.context(ptb), rt.PsychtoolboxKeyboard(keys=('D','J','KP9')) as backend:
            with backend.trial({'D':'conflict','J':'nonconflict','KP9':'pm'}) as w:
                self.assertEqual(w.held_keys,{'D','KP9'})
                w.mark_onset(100.01,1)
                ptb.pending.extend([dict(Keycode=7,Pressed=1,Time=100.),
                                    dict(Keycode=7,Pressed=1,Time=100.02),
                                    dict(Keycode=97,Pressed=0,Time=100.03),
                                    dict(Keycode=97,Pressed=1,Time=100.04)])
                w.consume(backend.drain())
                self.assertEqual(w.response,'pm')
                self.assertAlmostEqual(w.result()['rt_s'],.03,places=12)
                self.assertEqual(w.result()['n_ignored_pre_onset_keydowns'],0)

    def test_missing_backend_and_unconfigured_response_fail(self):
        from importlib.metadata import PackageNotFoundError
        with patch.object(rt,'version',side_effect=PackageNotFoundError('psychtoolbox')):
            with self.assertRaisesRegex(rt.TimingError,'No frame-polling fallback'):
                with rt.PsychtoolboxKeyboard(): self.fail()
        ptb,calls=self.fake_ptb()
        with self.context(ptb), rt.PsychtoolboxKeyboard() as backend:
            with self.assertRaises(rt.TimingError):
                with backend.trial({'9':'pm'}): self.fail()
        self.assertEqual(calls[-1][0],'KbQueueRelease')

    def fake_ptb(self, fail=None, events=()):
        calls = []
        pending = list(events)
        def hid(name, *args):
            calls.append((name, args))
            if name == fail:
                raise RuntimeError("native failure")
            if name == "KbCheck":
                return 0, 100., np.zeros((1, 256))
            if name == "KbQueueGetEvent":
                return (pending.pop(0), len(pending)) if pending else (np.empty((0, 0)), 0)
        return types.SimpleNamespace(GetSecs=lambda: 100.1, PsychHID=hid, pending=pending), calls

    def context(self, ptb, platform="darwin", backend_version=rt.PTB_VERSION):
        stack = ExitStack()
        stack.enter_context(patch.dict(sys.modules, psychtoolbox=ptb))
        stack.enter_context(patch.object(rt, "version", return_value=backend_version))
        stack.enter_context(patch.object(sys, "platform", platform))
        return stack

    def test_native_shapes_masks_and_cleanup_both_platforms(self):
        for platform in ("darwin", "win32"):
            ptb, calls = self.fake_ptb()
            with self.context(ptb, platform), rt.PsychtoolboxKeyboard(keys=rt.KEY_CODES["darwin"]) as backend:
                with backend.trial(KEYMAP) as w:
                    self.assertEqual(w.held_keys, set())
                    self.assertEqual(backend.drain(), [])
            mask = next(args[1] for name, args in calls if name == "KbQueueCreate")
            self.assertEqual(set(np.flatnonzero(mask) + 1), set(rt.KEY_CODES[platform].values()))
            self.assertEqual(calls[-1][0], "KbQueueRelease")
            self.assertEqual(sum(n == "KbQueueStart" for n, _ in calls), 2)

    def test_failed_startup_releases_queue_and_does_not_fallback(self):
        ptb, calls = self.fake_ptb(fail="KbCheck")
        with self.context(ptb), self.assertRaisesRegex(rt.TimingError, "No frame-polling fallback"):
            with rt.PsychtoolboxKeyboard():
                self.fail("Must not enter task with failed native input")
        self.assertEqual([n for n, _ in calls][-2:], ["KbQueueStop", "KbQueueRelease"])

    def test_adapter_preserves_native_timestamp_and_records_readout_separately(self):
        ptb, _ = self.fake_ptb()
        with self.context(ptb), rt.PsychtoolboxKeyboard(keys=rt.KEY_CODES["darwin"]) as backend:
            with backend.trial(KEYMAP) as w:
                w.mark_onset(100.05, 5)
                ptb.pending.extend([
                    dict(Keycode=7, Pressed=1, Time=100.075123456),
                    dict(Keycode=13, Pressed=1, Time=100.075623456),
                ])
                w.consume(backend.drain())
                self.assertEqual(w.response, "conflict")
                self.assertAlmostEqual(w.result()["rt_s"], .025123456, places=12)
                self.assertAlmostEqual(w.result()["response_readout_delay_s"], .024876544, places=12)

    def test_exception_inside_trial_stops_and_releases_native_queue(self):
        ptb, calls = self.fake_ptb()
        with self.context(ptb), self.assertRaises(SystemExit):
            with rt.PsychtoolboxKeyboard(keys=rt.KEY_CODES["darwin"]) as backend:
                with backend.trial(KEYMAP):
                    raise SystemExit()
        self.assertEqual([n for n, _ in calls][-2:], ["KbQueueStop", "KbQueueRelease"])

    def test_unvalidated_version_is_rejected(self):
        ptb, calls = self.fake_ptb()
        with self.context(ptb, backend_version="0.0"), self.assertRaises(rt.TimingError):
            with rt.PsychtoolboxKeyboard():
                self.fail()
        self.assertEqual(calls, [])


class FlashTests(unittest.TestCase):
    def test_flash_windows_use_visible_onsets_not_readout_or_offset(self):
        f = rt.FlashResponses(99, (), rt.PTB_VERSION)
        f.add_flash(100)
        f.add_flash(101)
        # Delayed retrieval after two visible flashes must still match the first.
        f.consume([event('SPACE', 99.9), event('SPACE', 99.95, False),
                   event('SPACE', 100.9995, lag=.1), event('SPACE', 100.9997, False),
                   event('SPACE', 101, lag=.1)])
        self.assertAlmostEqual(f.flashes[0]['rt'], .9995, places=12)
        self.assertEqual(f.flashes[1]['rt'], 0.)
        self.assertEqual(f.export(99)['flash_onsets'], '1;2')

    def test_repeats_held_keys_one_response_and_unanswered_flash(self):
        f = rt.FlashResponses(99, {'SPACE'}, rt.PTB_VERSION)
        f.add_flash(100)
        f.consume([event('SPACE', 100.1), event('9', 100.2), event('D', 100.3)])
        self.assertIsNone(f.flashes[0]['rt'])
        f.consume([event('SPACE', 100.4, False), event('SPACE', 100.500123456),
                   event('SPACE', 100.6), event('SPACE', 100.7, False), event('SPACE', 100.8)])
        self.assertAlmostEqual(f.flashes[0]['rt'], .500123456, places=12)
        f.add_flash(101)
        f.consume([event('SPACE', 101.1)])
        self.assertIsNone(f.flashes[1]['rt'])
        self.assertTrue(f.export(100)['flash_rts'].endswith(';NA'))

    def test_snapshot_and_trial_end_are_exclusive(self):
        f = rt.FlashResponses(99, (), rt.PTB_VERSION)
        f.add_flash(100)
        f.consume([event('SPACE', 99), event('SPACE', 100.5)], end_s=100.5)
        self.assertIsNone(f.flashes[0]['rt'])


class FakeTiming:
    backend_version = rt.PTB_VERSION

    def __init__(self, events=(), stall=0., held=(), draw_delay=.004):
        self.t = 1000.
        self.events = list(events)
        self.stall, self.held, self.draw_delay = stall, held, draw_delay
        self.active = False
        self.stopped = False
        self.closed = False
        self.frames = []
        self.flips = []
        self.trial_starts = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True

    def now(self):
        return self.t

    @contextmanager
    def trial(self, keymap):
        self.active = True
        self.trial_starts.append(self.t)
        try:
            yield rt.ResponseWindow(self.t, self.held, keymap, self.backend_version)
        finally:
            self.active = False
            self.stopped = True

    def drain(self):
        assert self.active
        ready = [e for e in self.events if e.timestamp_s <= self.t]
        self.events = [e for e in self.events if e.timestamp_s > self.t]
        return [rt.KeyEvent(e.key, e.pressed, e.timestamp_s, self.t) for e in ready]

    def tick(self, fps):
        dt = 1 / fps + self.stall
        self.t += dt
        return dt * 1000

    def draw(self, screen, font, info_font, trial, trial_idx, total_trials,
             elapsed, auto_delay, flash_on, aid_label_font, aid_font):
        assert self.active
        self.frames.append(dict(elapsed=elapsed, auto_delay=auto_delay, flash_on=flash_on,
                                drawn_s=self.t, trial=trial))
        self.t += self.draw_delay

    def flip(self):
        self.t += .003
        self.flips.append(self.t)


def trial_spec(**changes):
    kwargs = dict(
        pos1_start_x=300., pos1_start_y=200., vel1_x=100., vel1_y=0.,
        pos2_start_x=600., pos2_start_y=300., vel2_x=0., vel2_y=100.,
        route1_start_x=0., route1_start_y=200., route1_end_x=1280., route1_end_y=200.,
        route2_start_x=600., route2_start_y=0., route2_end_x=600., route2_end_y=720.,
        ac1_fl=370., ac2_fl=370., conflict_status='conflict', is_conflict=True,
        min_sep=16., guide_min_sep=40., deadline=10.,
        doms_nm=2., ttms=150., angle=90., ac1_speed=500., ac2_speed=500.,
        is_PM=False,
    )
    kwargs.update(changes)
    return task.TrialSpec(**kwargs)


class TaskIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def run_trial(self, timing, trial=None, pm=False, drt=False, flipped=False,
                  block=0, pygame_events=None, feedback_quit=False, own_backend=False,
                  fixation=False):
        task.apply_block_settings(task.BLOCKS[block])
        trial = trial or trial_spec()
        def feedback(*a, **k):
            self.assertFalse(timing.active)
            return {'quit': feedback_quit}
        def fix(*a, **k):
            self.assertFalse(timing.active)
            timing.t += .75
            return {'quit': False}
        with ExitStack() as stack:
            for name, value in (
                ('draw_response_frame', timing.draw), ('run_intertrial_screen', feedback),
                ('run_pretrial_fixation', fix), ('FIXATION_ON', fixation),
                ('KEY_CONFLICT', pygame.K_j if flipped else pygame.K_d),
                ('KEY_NONCONFLICT', pygame.K_d if flipped else pygame.K_j),
                ('sample_drt_flash_interval', lambda:.025), ('FLASH_DURATION', .030),
                ('draw_blank_radar', lambda *a, **k:None),
                ('draw_aid_banner_top_center', lambda *a, **k:None),
                ('time', types.SimpleNamespace(perf_counter=timing.now)),
            ):
                stack.enter_context(patch.object(task, name, value))
            stack.enter_context(patch.object(pygame.display, 'flip', timing.flip))
            stack.enter_context(patch.object(pygame.event, 'get', side_effect=pygame_events or (lambda:[])))
            stack.enter_context(patch.object(task, 'PsychtoolboxKeyboard', return_value=timing))
            row = task.run_trial(None, timing, None, None, None, trial, 1, 2, pm, drt,
                                 intertrial_every=0, timing=None if own_backend else timing)
        return row

    def test_early_first_flip_press_ignored_immediate_post_onset_retained(self):
        t = FakeTiming([event('D',1000.001),event('D',1000.002,False),event('J',1000.0075)])
        row = self.run_trial(t)
        self.assertAlmostEqual(row['stimulus_onset_s'],1000.007,places=11)
        self.assertEqual(row['response'],'nonconflict')
        self.assertAlmostEqual(row['rt_s'],.0005,places=11)
        self.assertEqual(row['n_ignored_pre_onset_keydowns'],1)
        self.assertTrue(t.stopped)
        self.assertEqual(t.frames[0]['elapsed'],0.)

    def test_readout_stalls_do_not_change_rt_or_accept_pygame_task_keys(self):
        for stall in (0,.008,.020,.050):
            t=FakeTiming([event('D',1000.157123456)],stall=stall)
            row=self.run_trial(t,pygame_events=lambda:[pygame.event.Event(pygame.KEYDOWN,key=pygame.K_j,mod=0)])
            self.assertEqual(row['response'],'conflict')
            self.assertAlmostEqual(row['rt_s'],.150123456,places=11)
            self.assertEqual(row['rt_ms'],1000*row['rt_s'])
            self.assertGreaterEqual(row['response_readout_delay_s'],0.)

    def test_both_mappings_all_blocks_pm_and_drt_modes(self):
        for block in range(4):
            for flipped in (False,True):
                for pm,drt in ((False,False),(False,True),(True,False),(True,True)):
                    t=FakeTiming([event('J' if flipped else 'D',1000.107)])
                    row=self.run_trial(t,flipped=flipped,pm=pm,drt=drt,block=block)
                    self.assertEqual(row['response'],'conflict')
                    self.assertEqual(row['correct'],1)
        for key in ('9','KP9'):
            for is_pm in (False,True):
                row=self.run_trial(FakeTiming([event(key,1000.1)]),trial=trial_spec(is_PM=is_pm),pm=True,drt=True)
                self.assertEqual(row['response'],'pm')
                self.assertEqual(row['correct'],int(is_pm))
            row=self.run_trial(FakeTiming([event(key,1000.1)]),trial=trial_spec(deadline=.2))
            self.assertEqual(row['response'],'TIMEOUT')

    def test_held_keys_release_repress_and_snapshot_events(self):
        for key in ('D','9','KP9'):
            t=FakeTiming([event(key,1000.),event(key,1000.01),event(key,1000.02,False),event(key,1000.03)],held={key})
            row=self.run_trial(t,pm=True)
            self.assertAlmostEqual(row['rt_s'],.023,places=11)
            self.assertEqual(row['n_ignored_pre_onset_keydowns'],0)

    def test_pm_competes_by_timestamp_and_space_never_completes_main(self):
        cases = [([event('D',1000.02),event('9',1000.01)],'pm'),
                 ([event('KP9',1000.02),event('J',1000.01)],'nonconflict'),
                 ([event('9',1000.01),event('D',1000.01)],'pm'),
                 ([event('SPACE',1000.01)],'TIMEOUT')]
        for events,expected in cases:
            row=self.run_trial(FakeTiming(events),pm=True,drt=True,trial=trial_spec(deadline=.1))
            self.assertEqual(row['response'],expected)

    def test_custom_deadlines_timestamp_boundaries_and_delayed_retrieval(self):
        for duration in (.025,.1,10.):
            for epsilon,expected in ((-1e-6,'conflict'),(0,'TIMEOUT'),(1e-6,'TIMEOUT')):
                t=FakeTiming(stall=.05)
                flip=t.flip
                def first_flip_event():
                    flip()
                    if len(t.flips)==1:
                        t.events.append(event('D',t.now()+duration+epsilon))
                t.flip=first_flip_event
                row=self.run_trial(t,trial=trial_spec(deadline=duration))
                self.assertEqual(row['response'],expected)
                self.assertEqual(row['deadline_s'],duration)
                if expected == 'TIMEOUT':
                    for field in ('rt_s','rt_ms','correct','response_timestamp_s','response_readout_delay_s'):
                        self.assertEqual(row[field],'')
                    self.assertEqual(row['outcome'],'too_slow')
                    self.assertEqual(row['feedback'],'TOO SLOW')
                else:
                    self.assertAlmostEqual(row['rt_s'],duration-1e-6,places=11)

    def test_slow_preparation_does_not_consume_deadline(self):
        t=FakeTiming([event('D',1000.056)],draw_delay=.050)
        row=self.run_trial(t,trial=trial_spec(deadline=.01))
        self.assertAlmostEqual(row['stimulus_onset_s'],1000.053,places=11)
        self.assertAlmostEqual(row['rt_s'],.003,places=11)

    def test_advice_delays_and_fixation_do_not_advance_first_frame(self):
        for delay in (-.05,0.,.05,.5):
            t=FakeTiming([event('D',1001.1)])
            row=self.run_trial(t,trial=trial_spec(automation='conflict',auto_delay=delay),block=2,fixation=True)
            self.assertEqual(t.frames[0]['elapsed'],0.)
            self.assertGreaterEqual(row['stimulus_onset_s'],1000.757)
            self.assertEqual(row['aid_onset_s'],delay)
            self.assertEqual(row['aid_onset_ms'],round(delay*1000,0))
            self.assertEqual(t.frames[0]['auto_delay'],max(0.,delay))
            self.assertAlmostEqual(row['rt_s'],1001.1-row['stimulus_onset_s'])
            if delay==.5:
                self.assertTrue(all(f['elapsed'] < .5 for f in t.frames))
            for frame in t.frames[1:]:
                self.assertAlmostEqual(frame['elapsed'],frame['drawn_s']-row['stimulus_onset_s'])

    def test_space_before_new_flash_not_assigned_to_it(self):
        # First flash is flipped at 1000.0543333333: two ticks plus three draw/flips.
        t=FakeTiming([event('SPACE',1000.05),event('SPACE',1000.056,False),
                      event('SPACE',1000.060123456),event('D',1000.2)])
        row=self.run_trial(t,drt=True,pm=True)
        first_flash_index=next(i for i,f in enumerate(t.frames) if f['flash_on'])
        visible=t.flips[first_flash_index]
        self.assertAlmostEqual(visible,1000.0543333333334,places=10)
        self.assertAlmostEqual(float(row['flash_rts'].split(';')[0]),1000.060123456-visible,places=11)
        self.assertAlmostEqual(float(row['flash_onsets'].split(';')[0]),visible-row['stimulus_onset_s'],places=11)
        self.assertEqual(row['response'],'conflict')

    def test_hard_quit_before_after_onset_and_feedback_cleanup(self):
        quit_event=pygame.event.Event(pygame.KEYDOWN,key=pygame.K_q,mod=pygame.KMOD_ALT)
        for batches in ([[quit_event]],[[],[quit_event]]):
            t=FakeTiming()
            row=self.run_trial(t,pygame_events=batches,own_backend=True)
            self.assertEqual(row,{'quit':True})
            self.assertTrue(t.stopped and t.closed)
        t=FakeTiming([event('D',1000.1)])
        self.assertEqual(self.run_trial(t,feedback_quit=True,own_backend=True),{'quit':True})
        self.assertTrue(t.stopped and t.closed)

    def test_render_and_queue_errors_cleanup_without_fallback(self):
        for where in ('draw','drain'):
            t=FakeTiming()
            def fail(*a,**k): raise RuntimeError('deliberate failure')
            setattr(t,where,fail)
            with self.assertRaisesRegex(RuntimeError,'deliberate failure'):
                self.run_trial(t,own_backend=True)
            self.assertTrue(t.stopped and t.closed)

    def test_design_constants_counterbalance_and_staircase_unchanged(self):
        self.assertEqual([b['N_TRIALS'] for b in task.BLOCKS],[300,500,500,500])
        self.assertEqual([b['AUTOMATION_ACC'] for b in task.BLOCKS],[1.,1.,.95,.65])
        self.assertTrue(all(b['TARGET_ACC']==.8 and not b['DRT_ON'] for b in task.BLOCKS))
        self.assertEqual(task.DEADLINE_SEC,10.)
        orders={tuple(task.counterbalanced_block_ordering(pid)[0]) for pid in range(1,13)}
        self.assertEqual(len(orders),6)
        app=task.ATCLabApp.__new__(task.ATCLabApp)
        app.staircase=task.DomGapStaircase(on=True,target_acc=.8)
        before=app.staircase.gap_nm
        app._update_staircase_from_result(trial_spec(),{'correct':1})
        self.assertLess(app.staircase.gap_nm,before)
        before=app.staircase.gap_nm
        app._update_staircase_from_result(trial_spec(is_PM=True),{'correct':0})
        self.assertEqual(app.staircase.gap_nm,before)

    def test_real_drawing_initial_positions_and_motion(self):
        task.apply_block_settings(task.BLOCKS[0])
        screen=pygame.Surface((1280,720))
        font=pygame.font.Font(None,20)
        original=pygame.draw.circle
        for elapsed,expected in ((0.,[(300,200),(600,300)]),(.25,[(325,200),(600,325)])):
            aircraft=[]
            def circle(surface,color,center,radius,*a,**k):
                if radius==task.CIRCLE_RADIUS: aircraft.append(center)
                return original(surface,color,center,radius,*a,**k)
            with patch.object(pygame.draw,'circle',circle):
                task.draw_response_frame(screen,font,font,trial_spec(),0,1,elapsed,0,False,font,font)
            self.assertEqual(aircraft,expected)

    @unittest.skipUnless(shutil.which('Rscript'),'Rscript required for actual collation')
    def test_fixed_writers_and_real_mixed_historical_collation(self):
        old=self.run_trial(FakeTiming([event('D',1000.1)]))
        old.update(participant_id=1,block='MANUAL',block_idx=2,
                   aid_accuracy_setting=.95,aid_label='conflict',aid_correct=1)
        for key in rt.AUDIT_FIELDS: old.pop(key)
        old['rt_s']=-.012345678901234
        zero=dict(old,trial_idx=3,rt_s=0.)
        historical_timeout=dict(old,trial_idx=4,response='TIMEOUT',rt_s=10.,outcome='too_slow')
        new=[]
        for i,stamp in enumerate((1000.157123456789,1000.157623456789),1):
            row=self.run_trial(FakeTiming([event('D',stamp),event('SPACE',1000.060123456789+(i-1)*.0005)]),drt=True)
            row.update(participant_id=2,trial_idx=i,block='MANUAL',block_idx=2,
                       aid_accuracy_setting=.95,aid_label='conflict',aid_correct=1)
            new.append(row)
        timeout=self.run_trial(FakeTiming(stall=.05),trial=trial_spec(deadline=.025))
        timeout.update(participant_id=2,trial_idx=3,block='MANUAL',block_idx=2,
                       aid_accuracy_setting=.95,aid_label='conflict',aid_correct=1)
        new.append(timeout)
        with tempfile.TemporaryDirectory() as td:
            source=Path(td)/'source'; source.mkdir()
            dest=Path(td)/'collated'
            write_rows(source/'results_p001_20260101_120000_b00_ALL.csv',[old,zero,historical_timeout])
            # Existing selection is by mtime (independently for each file family).
            older=source/'results_p001_20270101_120000_b00_ALL.csv'
            write_rows(older,[dict(old,rt_s=999.)]); os.utime(older,(1,1))
            app=task.ATCLabApp.__new__(task.ATCLabApp)
            app.results=new; app.all_results=new
            app.base_with_participant=lambda:'p002_20260101_120000'
            with patch.object(task,'RESULTS_DIR',str(source)):
                raw=app.save_results_csv(block_order=2,block_name='MANUAL')
                combined=app.save_combined_results_csv()
            for filename in (raw,combined):
                with open(filename) as f: restored=list(csv.DictReader(f))
                self.assertEqual(set(restored[0]),set(task.ALL_RESULT_FIELDS))
                for expected,actual in zip(new,restored):
                    for field in ('rt_s','rt_ms',*rt.AUDIT_FIELDS):
                        self.assertEqual(str(expected[field]),actual[field])
                self.assertAlmostEqual(float(restored[1]['rt_s'])-float(restored[0]['rt_s']),.0005,places=11)
            for pid in (1,2):
                for suffix in ('POSTBLOCK_ALL','POSTBLOCK_SLIDERS_ALL'):
                    path=source/f'results_p{pid:03d}_20260101_120000_b00_{suffix}.csv'
                    write_rows(path,[dict(participant_id=pid,block='MANUAL',response=pid+3)])
            run=subprocess.run([shutil.which('Rscript'),str(ROOT/'collate_data.R'),str(source),str(dest)],
                               cwd=td,capture_output=True,text=True,timeout=60)
            self.assertEqual(run.returncode,0,run.stderr[-5000:])
            for name in ('data_atc_all.csv','data_atc.csv'):
                with (dest/name).open() as f: rows=list(csv.DictReader(f))
                self.assertEqual(len(rows),6)
                historical=[r for r in rows if r['participant_id']=='1']
                self.assertEqual([float(r['rt_s']) for r in historical],[old['rt_s'],0.,10.])
                self.assertTrue(all(r[k] in ('','NA') for r in historical for k in rt.AUDIT_FIELDS))
                current=sorted((r for r in rows if r['participant_id']=='2'),key=lambda r:int(r['trial_idx']))
                for i,expected_rt in enumerate((.150123456789,.150623456789)):
                    self.assertAlmostEqual(float(current[i]['rt_s']),expected_rt,places=10)
                    self.assertEqual(current[i]['rt_timing_version'],rt.TIMING_VERSION)
                    self.assertEqual(current[i]['rt_backend_version'],rt.PTB_VERSION)
                    self.assertAlmostEqual(float(current[i]['response_timestamp_s'])-float(current[i]['stimulus_onset_s']),expected_rt,places=10)
                self.assertAlmostEqual(float(current[1]['rt_s'])-float(current[0]['rt_s']),.0005,places=10)
                self.assertIn(current[2]['rt_s'],('','NA'))
                if name=='data_atc_all.csv':
                    self.assertTrue({'is_PM','flash_onsets','flash_rts','TTMS','angle_deg'}<=set(rows[0]))
                    flash_rts=[float(r['flash_rts'].split(';')[0]) for r in current[:2]]
                    self.assertAlmostEqual(flash_rts[1]-flash_rts[0],.0005,places=10)
                    self.assertAlmostEqual(flash_rts[0],.060123456789-(.007+2*(1/60+.007)),places=10)
            for name in ('data_atc_postblock_all.csv','data_atc_sliders_all.csv'):
                with (dest/name).open() as f: rows=list(csv.DictReader(f))
                self.assertEqual({r['participant_id']:r['response'] for r in rows},{'1':'4','2':'5'})
            historical_source=Path(td)/'historical'; historical_source.mkdir()
            for path in source.glob('results_p001*'):
                shutil.copy2(path,historical_source/path.name)
            historical_dest=Path(td)/'historical_collated'
            run=subprocess.run([shutil.which('Rscript'),str(ROOT/'collate_data.R'),str(historical_source),str(historical_dest)],
                               cwd=td,capture_output=True,text=True,timeout=60)
            self.assertEqual(run.returncode,0,run.stderr[-3000:])
            for name in ('data_atc_all.csv','data_atc.csv'):
                with (historical_dest/name).open() as f: rows=list(csv.DictReader(f))
                self.assertEqual([float(r['rt_s']) for r in rows],[old['rt_s'],0.,10.])
                self.assertTrue(set(rt.AUDIT_FIELDS).isdisjoint(rows[0]))


if __name__ == '__main__':
    unittest.main()
