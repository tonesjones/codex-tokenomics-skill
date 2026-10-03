"""Fixture tests. Live metadata verification is recorded separately in CHECKPOINT.md."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'skills' / 'tokenomics'))
from tokenomics_router import (route_task, record_result, summarize_usage, associate_sessions,
                              collect_session, collect_usage, record_comparison, record_account_snapshot)


def stamp(n):
    return f'2026-10-03T20:00:{n:02d}+00:00'


def tokens(n, inputs, cached, outputs, last=None):
    total = dict(input_tokens=inputs, cached_input_tokens=cached, output_tokens=outputs)
    return dict(timestamp=stamp(n), type='event_msg', payload=dict(type='token_count',
                info=dict(total_token_usage=total, last_token_usage=last)))


class TokenomicsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.log = self.root / 'usage.jsonl'
        self.config = dict(log_path=self.log)

    def decision(self, delegate=False):
        d = route_task('Collect sources', dict(current_model='gpt-6.1-sol', work_scope='substantial' if delegate else 'small', independent=True))
        record_result(d, dict(stage='checkpoint'), config=self.config)
        return d

    def session(self, identity, model='gpt-6.1-sol', role='parent', events=None, start=None, end=stamp(4)):
        path = self.root / (identity + '.jsonl')
        rows = [dict(type='session_meta', payload=dict(id=identity)),
                dict(type='turn_context', timestamp=stamp(0), payload=dict(model=model, effort='medium'))]
        rows += events if events is not None else [tokens(1, 100, 60, 10), tokens(2, 150, 80, 20),
                                                   dict(type='event_msg', timestamp=stamp(4), payload=dict(type='task_complete'))]
        # Sensitive content must never appear in measurements.
        rows.append(dict(type='response_item', payload=dict(secret='DO_NOT_STORE_PROMPT_OR_SOURCE')))
        path.write_text('\n'.join(json.dumps(r) for r in rows), encoding='utf-8')
        return dict(path=str(path), session_id=identity, role=role,
                    purpose='task_owner' if role == 'parent' else 'tokenomics',
                    reason='Owner' if role == 'parent' else 'Bounded collection', start=start, end=end,
                    cache_condition='observed warm')

    def test_routing_scope_difficulty_and_identity(self):
        for task in ('Plan a migration', 'Assess security', 'Collect sources and decide changes'):
            self.assertEqual(route_task(task, dict(current_model='gpt-6.1-sol', work_scope='substantial', independent=True))['action'], 'stay')
        d = self.decision(True)
        self.assertEqual((d['action'], d['tier']), ('delegate', 'cheap'))
        self.assertEqual(self.decision()['action'], 'stay')
        hard = route_task('tests', dict(current_model='gpt-6.1-sol', work_scope='substantial', independent=True,
                                        assessment=dict(task_type='test', complexity=.9, confidence=1)))
        self.assertEqual(hard['candidate_tier'], 'standard')
        unknown = route_task('collect sources', dict(current_model='unknown'))
        self.assertEqual(unknown['status'], 'needs_model_identity')
        self.assertEqual(unknown['action'], 'stay')
        legacy = route_task('security', dict(current_model='gpt-6-sol'))
        self.assertEqual(legacy['tier'], 'standard')

    def test_astra_and_classifier_fallback(self):
        d = route_task('work', dict(current_model='gpt-6.1-sol', force_strong=True))
        self.assertEqual(d['action'], 'request_approval')
        approved = route_task('work', dict(current_model='gpt-6.1-sol', force_strong=True, approval_granted=True))
        self.assertEqual(approved['action'], 'delegate')
        def broken(*args):
            raise RuntimeError('offline')
        self.assertFalse(route_task('work', config=dict(classifier=broken))['classifier_available'])

    def test_pairing_preserves_tier_and_original_fields(self):
        d = self.decision(True)
        altered = {**d, 'model': 'gpt-6.1-sol', 'tier': 'standard', 'task_type': 'integration', 'deliverable': 'replacement'}
        o = record_result(altered, dict(tier='standard', model='replacement', task_accepted=True,
                                       child_output_usable=False, escalated=True, retries=1, recovery=True,
                                       prompts='DO_NOT_STORE_PROMPT_OR_SOURCE'), config=self.config)
        for key in ('model', 'tier', 'task_type', 'deliverable', 'decision_id'):
            self.assertEqual(o[key], d[key])
        self.assertNotIn('prompts', o)
        report = summarize_usage(self.log)
        self.assertEqual(report['accepted_results'], 1)
        self.assertEqual(report['child_outputs_usable'], 0)
        self.assertEqual(report['escalation_frequency'], 1)
        self.assertEqual(report['results'][0]['retries'], 1)
        self.assertEqual(report['completed_outcomes'], 1)
        self.assertEqual(report['coverage']['complete_decisions'], 0)

    def test_checkpoint_not_outcome_and_retrospective(self):
        d = route_task('Work', dict(current_model='gpt-6.1-sol'))
        row = record_result(d, dict(stage='checkpoint', retrospective=True), config=self.config)
        self.assertTrue(row['retrospective'])
        self.assertEqual(summarize_usage(self.log)['completed_outcomes'], 0)
        record_result(d, dict(task_accepted=False, child_output_usable=True, escalated=False), config=self.config)
        self.assertEqual(summarize_usage(self.log)['child_outputs_usable'], 1)
        self.assertEqual(summarize_usage(self.log)['accepted_results'], 0)

    def test_orphan_and_missing_measurements(self):
        d = route_task('Work')
        with self.assertRaises(ValueError):
            record_result(d, {}, True, self.config)
        with self.assertRaises(ValueError):
            record_result({}, {})
        d = self.decision()
        record_result(d, {}, config=self.config)
        m = collect_usage(self.log, d['decision_id'])
        self.assertFalse(m['complete'])
        report = summarize_usage(self.log)
        self.assertIsNone(report['subscription_savings'])
        self.assertIsNone(report['baseline_savings'])
        self.assertIsNone(report['escalation_frequency'])
        self.assertEqual(report['acceptance_unknown'], 1)
        self.assertEqual(report['completed_outcomes'], 0)
        self.assertEqual(report['outcome_records'], 1)
        self.assertIsNone(report['elapsed_seconds'])

    def test_cumulative_duplicates_cached_subset_and_reset(self):
        reset = dict(input_tokens=20, cached_input_tokens=5, output_tokens=3)
        events = [tokens(1, 100, 60, 10), tokens(1, 100, 60, 10), tokens(2, 100, 60, 10),
                  tokens(3, 150, 80, 20), tokens(4, 20, 5, 3, reset), tokens(5, 40, 10, 5)]
        m = collect_session(self.session('s', events=events, end=stamp(5)))
        self.assertEqual(m['models']['gpt-6.1-sol'], dict(input_tokens=190, cached_input_tokens=90, output_tokens=25))
        self.assertEqual(m['counter_resets'], 1)
        self.assertTrue(m['complete'])
        self.assertEqual(m['elapsed_seconds'], 5)

    def test_ambiguous_reset_and_missing_cache_are_unknown(self):
        m = collect_session(self.session('s', events=[tokens(1, 100, 60, 10), tokens(4, 5, 0, 1)]))
        self.assertIsNone(m['models']['gpt-6.1-sol']['input_tokens'])
        self.assertFalse(m['complete'])
        m = collect_session(self.session('x', events=[tokens(4, 100, None, 10)]))
        self.assertEqual(m['models']['gpt-6.1-sol']['input_tokens'], 100)
        self.assertIsNone(m['models']['gpt-6.1-sol']['cached_input_tokens'])
        self.assertFalse(m['complete'])

    def test_bounds_subtract_baseline_and_reject_ambiguous_start(self):
        s = self.session('s', start=stamp(1), end=stamp(2))
        m = collect_session(s)
        self.assertEqual(m['models']['gpt-6.1-sol'], dict(input_tokens=50, cached_input_tokens=20, output_tokens=10))
        self.assertEqual(m['elapsed_seconds'], 1)
        self.assertTrue(m['complete'])
        s['start'] = '2026-10-03T20:00:01.500+00:00'
        m = collect_session(s)
        self.assertFalse(m['complete'])
        self.assertIsNone(m['models']['gpt-6.1-sol']['input_tokens'])

    def test_identity_fork_and_open_interval(self):
        s = self.session('s')
        s['session_id'] = 'wrong'
        self.assertEqual(collect_session(s)['models'], {})
        s['session_id'] = 's'
        s['end'] = None
        self.assertTrue(collect_session(s)['complete']) # observed task completion
        s = self.session('open', events=[tokens(1, 100, 60, 10)], end=None)
        self.assertFalse(collect_session(s)['complete'])
        self.assertIsNone(collect_session(s)['elapsed_seconds'])
        p = Path(s['path'])
        rows = p.read_text().splitlines()
        row = json.loads(rows[0]); row['payload']['forked_from_id'] = 'parent'; rows[0] = json.dumps(row)
        p.write_text('\n'.join(rows))
        self.assertIsNone(collect_session(s)['models']['gpt-6.1-sol']['input_tokens'])

    def test_parent_and_all_children_aggregation_and_reaudit(self):
        d = self.decision(True)
        parent = self.session('parent')
        child = self.session('child', 'gpt-6-luna', 'child')
        review = self.session('review', 'gpt-6.1-sol', 'child')
        review.update(purpose='required_review', reason='Another skill requires review')
        associate_sessions(d, [parent, child, review], self.config, all_children_accounted=True)
        a = collect_usage(self.log, d['decision_id'])
        self.assertTrue(a['complete'])
        self.assertEqual(a['models']['gpt-6.1-sol']['input_tokens'], 300)
        self.assertEqual(a['models']['gpt-6-luna']['input_tokens'], 150)
        self.assertEqual(a['elapsed_seconds'], 4)
        self.assertEqual(a['session_seconds'], 12)
        self.assertEqual(a['sessions'][2]['purpose'], 'required_review')
        self.assertNotIn('DO_NOT_STORE_PROMPT_OR_SOURCE', json.dumps(a))
        self.assertNotIn('path', a['sessions'][0])
        self.assertIsNone(a['sessions'][0]['retries'])
        collect_usage(self.log, d['decision_id'])
        report = summarize_usage(self.log)
        self.assertEqual(report['models']['gpt-6.1-sol']['measured_input_tokens'], 300)
        self.assertEqual(report['coverage']['measured_decisions'], 1)

    def test_incomplete_children_and_unavailable_session(self):
        d = self.decision()
        associate_sessions(d, [self.session('parent')], self.config)
        self.assertFalse(collect_usage(self.log, d['decision_id'])['complete'])
        s = self.session('missing'); Path(s['path']).unlink()
        self.assertEqual(collect_session(s)['issues'], ['session unavailable'])
        with self.assertRaises(ValueError):
            associate_sessions(d, [self.session('p'), self.session('p')])

    def test_overlap_not_double_counted(self):
        for i in range(2):
            d = self.decision()
            associate_sessions(d, [self.session('parent')], self.config, all_children_accounted=True)
            collect_usage(self.log, d['decision_id'])
        report = summarize_usage(self.log)
        self.assertTrue(report['overlapping_decision_intervals'])
        self.assertIsNone(report['models'])

    def test_optional_pair_reports_observations_and_conditions(self):
        a, b = self.decision(), self.decision(True)
        for d, sessions in ((a, [self.session('sol')]), (b, [self.session('owner'), self.session('luna', 'gpt-6-luna', 'child')])):
            associate_sessions(d, sessions, self.config, all_children_accounted=True)
            collect_usage(self.log, d['decision_id'])
            record_result(d, dict(child_output_usable=True, escalated=False), True, self.config)
        record_comparison(self.log, a['decision_id'], b['decision_id'], task_key='equivalent-fixture',
                          acceptance_checks=['same literal check'], equivalent_tasks=True,
                          includes_coordination_review_recovery=True)
        report = summarize_usage(self.log)
        pair = report['comparisons'][0]
        self.assertTrue(pair['comparable_observations'])
        self.assertEqual(pair['arms']['sol_luna']['tokens_per_accepted_result']['gpt-6.1-sol']['input_tokens'], 150)
        self.assertEqual(pair['arms']['sol_only']['seconds_per_accepted_result'], 4)
        self.assertEqual(pair['arms']['sol_only']['effort_and_cache'][0]['efforts'][0]['effort'], 'medium')
        self.assertIsNone(pair['subscription_savings'])
        record_result(b, dict(task_accepted=False), config=self.config)
        self.assertFalse(summarize_usage(self.log)['comparisons'][0]['comparable_observations'])

    def test_account_snapshot_label_and_unknown_legacy(self):
        r = record_account_snapshot(self.log, dict(used_percent=20, secret='not stored'))
        self.assertEqual(r['scope'], 'account-wide')
        self.assertNotIn('secret', r)
        with self.log.open('a') as handle:
            handle.write(json.dumps(dict(stage='outcome', success=True, tier='cheap'))+'\n')
        report = summarize_usage(self.log)
        self.assertEqual(report['unpaired_legacy_records'], 1)
        self.assertEqual(report['accepted_results'], 0)

    def test_multiple_observed_models_and_explicit_runtime_events(self):
        events = [tokens(1, 100, 50, 10),
                  dict(type='turn_context', timestamp=stamp(2), payload=dict(model='gpt-6-luna', effort='low')),
                  tokens(3, 150, 70, 20),
                  dict(type='event_msg', timestamp=stamp(4), payload=dict(type='retry', event_id='r')),
                  dict(type='event_msg', timestamp=stamp(4), payload=dict(type='retry', event_id='r')),
                  dict(type='event_msg', timestamp=stamp(5), payload=dict(type='recovery_started'))]
        m = collect_session(self.session('s', events=events, end=stamp(5)))
        self.assertEqual(m['models']['gpt-6.1-sol']['input_tokens'], 100)
        self.assertEqual(m['models']['gpt-6-luna']['input_tokens'], 50)
        self.assertEqual(m['retries'], 1)
        self.assertTrue(m['recovery'])
        self.assertEqual(m['efforts'][1]['effort'], 'low')

    def test_last_usage_only_missing_identity_and_resumed_session(self):
        event = tokens(1, 100, 50, 10)
        event['payload']['info']['total_token_usage'] = None
        m = collect_session(self.session('s', events=[event], end=stamp(1)))
        self.assertFalse(m['complete'])
        self.assertEqual(m['models'], {})
        s = self.session('resume', events=[tokens(1, 100, 50, 10),
                        dict(type='event_msg', timestamp=stamp(2), payload=dict(type='task_complete')),
                        dict(type='event_msg', timestamp=stamp(3), payload=dict(type='task_started')),
                        tokens(4, 200, 100, 20)], end=None)
        self.assertFalse(collect_session(s)['complete'])
        self.assertIsNone(collect_session(s)['elapsed_seconds'])

    def test_children_outside_parent_bounds_are_incomplete(self):
        d = self.decision(True)
        associate_sessions(d, [self.session('p', end=stamp(2)), self.session('c', 'gpt-6-luna', 'child')],
                           self.config, all_children_accounted=True)
        m = collect_usage(self.log, d['decision_id'])
        self.assertFalse(m['child_bounds_fit_parent'])
        self.assertFalse(m['complete'])

    def test_unknown_model_and_invalid_cache(self):
        s = self.session('no-model', model=None)
        m = collect_session(s)
        self.assertIn('unknown', m['models'])
        self.assertFalse(m['complete'])
        m = collect_session(self.session('bad-cache', events=[tokens(4, 10, 11, 2)]))
        self.assertIsNone(m['models']['gpt-6.1-sol']['cached_input_tokens'])
        self.assertFalse(m['complete'])

    def test_no_duplicate_token_counts_and_reject_bad_outcome(self):
        d = self.decision(True)
        record_result(d, dict(task_accepted=True, escalated=False), config=self.config)
        record_result(d, dict(task_accepted=True, escalated=False), config=self.config)
        self.assertEqual(summarize_usage(self.log)['accepted_results'], 1)
        with self.assertRaises(ValueError):
            record_result(d, dict(retries='unknown'), config=self.config)
        with self.assertRaises(ValueError):
            record_result(d, dict(task_accepted='true'), config=self.config)

    def test_association_change_requires_new_measurement(self):
        d = self.decision()
        s = self.session('parent')
        associate_sessions(d, [s], self.config, all_children_accounted=True)
        collect_usage(self.log, d['decision_id'])
        self.assertEqual(summarize_usage(self.log)['coverage']['measured_decisions'], 1)
        associate_sessions(d, [s], self.config, all_children_accounted=None)
        self.assertEqual(summarize_usage(self.log)['coverage']['measured_decisions'], 0)

    def test_future_end_is_unknown_and_zero_child_context_has_parent_estimate(self):
        s = self.session('s', end=stamp(9))
        self.assertIsNone(collect_session(s)['elapsed_seconds'])
        self.assertFalse(collect_session(s)['complete'])
        d = route_task('Collect sources', dict(current_model='gpt-6.1-sol',
                       handoff_context_tokens=0, handoff_read_tokens=0))
        self.assertGreater(d['estimates']['cheap']['estimated_parent_input_tokens'], 0)
        self.assertEqual(d['estimates']['stay']['estimated_parent_input_tokens'], 0)

    def test_cloud_metadata_unavailable_is_unknown(self):
        d = self.decision(True)
        associate_sessions(d, [dict(session_id='cloud-runtime-id', path=None, role='parent',
                           purpose='task_owner', reason='Cloud task owner', environment='cloud')],
                           self.config, all_children_accounted=True)
        m = collect_usage(self.log, d['decision_id'])
        self.assertFalse(m['complete'])
        self.assertEqual(m['models'], {})
        self.assertEqual(m['sessions'][0]['environment'], 'cloud')
        self.assertIn('usage unknown', m['sessions'][0]['issues'][0])
        self.assertIsNone(m['elapsed_seconds'])
        self.assertIsNone(summarize_usage(self.log)['subscription_savings'])

    def test_skill_only_installer_backups_and_preserves_other_files(self):
        script = Path(__file__).parents[1] / 'install_skill.py'
        target = self.root / 'project' / '.agents' / 'skills' / 'tokenomics'
        command = [sys.executable, str(script), '--repo-root', str(self.root / 'project'),
                   '--backup-root', str(self.root / 'backups')]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        self.assertEqual(Path(json.loads(result.stdout)['target']), target.resolve())
        original = (target / 'SKILL.md').read_bytes()
        (target / 'SKILL.md').write_text('old skill', encoding='utf-8')
        (target / 'personal.txt').write_text('keep me', encoding='utf-8')
        unrelated = self.root / 'project' / 'AGENTS.md'
        unrelated.write_text('unchanged', encoding='utf-8')
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        report = json.loads(result.stdout)
        self.assertEqual((Path(report['backup']) / 'SKILL.md').read_text(), 'old skill')
        self.assertEqual((target / 'SKILL.md').read_bytes(), original)
        self.assertEqual((target / 'personal.txt').read_text(), 'keep me')
        self.assertEqual(unrelated.read_text(), 'unchanged')
        self.assertFalse((self.root / 'project' / 'config.toml').exists())
        self.assertEqual(len(report['sha256']), 3)

    def test_cli_checkpoint_and_summary(self):
        script = Path(__file__).parents[1] / 'skills' / 'tokenomics' / 'tokenomics_router.py'
        command = [sys.executable, str(script)]
        run = subprocess.run(command + ['--current-model', 'gpt-6.1-sol', '--work-scope', 'substantial', '--independent',
                                        '--task-type', 'source_collection', '--log', str(self.log), 'Collect evidence'], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(run.stdout)['action'], 'delegate')
        run = subprocess.run(command + ['--summary', '--log', str(self.log)], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(run.stdout)['completed_outcomes'], 0)


if __name__ == '__main__':
    unittest.main()
