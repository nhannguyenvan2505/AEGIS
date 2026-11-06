"""Changed observation evidence must not authorize a new closure."""
import unittest
import hashlib
import json
import test_followup


class EvidenceRecheckTests(unittest.TestCase):
    setUp = test_followup.FollowupTests.setUp
    create = test_followup.FollowupTests.create
    command = test_followup.FollowupTests.command

    def checked(self):
        c = self.create()
        self.assertEqual(self.command(c['id'], 1, 'acknowledge')[0].status_code, 201)
        r = self.command(c['id'], 2, 'check')[0]
        self.assertEqual(r.status_code, 201)
        return c, r.json['event']

    def edit(self, status='active'):
        p = {k:self.payload[k] for k in ['finding','notes','analysis_id','review','record_status','change_reason']}
        p.update(base_revision=1, finding='present', record_status=status, change_reason='Correct synthetic evidence')
        r = self.client.put('/api/farm/observations/'+self.visit['id'], json=p, headers=self.headers[0])
        self.assertEqual(r.status_code, 201)
        return r.json['item']

    def test_edited_observation_blocks_close_until_rechecked(self):
        c, frozen = self.checked()
        self.edit()
        r = self.command(c['id'], 3, 'close')[0]
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json['error']['code'], 'followup_observation_changed')
        r = self.command(c['id'], 3, 'check')[0]
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json['event']['payload']['observation_snapshot']['revision'], 2)
        self.assertEqual(self.command(c['id'], 4, 'close')[0].status_code, 201)
        events = self.client.get('/api/farm/follow-ups/'+c['id']+'/events', headers=self.headers[0]).json['items']
        self.assertEqual(next(e for e in events if e['version']==3), frozen)

    def test_voided_observation_blocks_close_and_cannot_be_rechecked(self):
        c, frozen = self.checked()
        self.edit('voided')
        self.assertEqual(self.command(c['id'], 3, 'close')[0].status_code, 409)
        self.assertEqual(self.command(c['id'], 3, 'check')[0].status_code, 400)
        item = self.client.get('/api/farm/follow-ups/'+c['id'], headers=self.headers[0]).json['item']
        self.assertEqual(item['version'], 3)
        self.assertEqual(item['state'], 'checked')
        events = self.client.get('/api/farm/follow-ups/'+c['id']+'/events', headers=self.headers[0]).json['items']
        self.assertEqual(events[0], frozen)

    def test_closed_case_stays_closed_after_source_change_and_reads_are_pure(self):
        c, frozen = self.checked()
        self.assertEqual(self.command(c['id'], 3, 'close')[0].status_code, 201)
        self.edit()
        paths=[self.root/name for name in ['demo.db','journal.sqlite3','followup.sqlite3']]
        before=[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths]
        item=self.client.get('/api/farm/follow-ups/'+c['id'],headers=self.headers[0]).json['item']
        self.assertEqual(item['state'],'closed');self.assertEqual(item['version'],4)
        self.assertEqual(item['check_status']['reasons'],['observation_changed'])
        self.assertEqual(item['check_status']['observation']['checked_revision'],1)
        self.assertEqual(item['check_status']['observation']['current_revision'],2)
        self.assertEqual(before,[hashlib.sha256(p.read_bytes()).hexdigest() for p in paths])

    def test_replaying_old_check_cannot_accept_new_revision_or_bypass_close_guard(self):
        c=self.create();self.command(c['id'],1,'acknowledge')
        first,command=self.command(c['id'],2,'check');self.assertEqual(first.status_code,201)
        self.edit()
        replay=self.client.post('/api/farm/follow-ups/'+c['id']+'/events',json=command,headers=self.headers[0])
        self.assertEqual(replay.status_code,200);self.assertEqual(replay.json['event'],first.json['event'])
        self.assertEqual(replay.json['item']['version'],3)
        self.assertTrue(replay.json['item']['check_status']['needs_recheck'])
        self.assertEqual(self.command(c['id'],3,'close')[0].status_code,409)
        for owner in [None,1]:
            r=self.client.get('/api/farm/follow-ups/'+c['id'],headers=self.headers[owner] if owner else {})
            self.assertEqual(r.status_code,401 if owner is None else 404)


class GroupEvidenceTests(unittest.TestCase):
    def test_episode_reports_source_change_without_rewriting_check(self):
        import test_episodes
        fixture=test_episodes.EpisodeTests('test_successive_hours_group_and_manual_lookup_preserve_snapshots')
        fixture.setUp()
        try:
            job,run=fixture.start();cid=run['followup_id'];obs=fixture.observation(fixture.at[0])
            fixture.action(cid,1,'acknowledge');frozen=fixture.action(cid,2,'check',obs).json['event']
            current=fixture.client.get('/api/farm/observations/'+obs,headers=fixture.headers[0]).json['item']
            p={k:current['payload'][k] for k in ['finding','notes','analysis_id','review','record_status']}
            p.update(base_revision=1,notes='Corrected notes',change_reason='Synthetic revision')
            self.assertEqual(fixture.client.put('/api/farm/observations/'+obs,json=p,headers=fixture.headers[0]).status_code,201)
            ep=fixture.episodes().json['items'][0]
            self.assertTrue(ep['needs_recheck']);self.assertEqual(ep['check_status']['reasons'],['observation_changed'])
            self.assertEqual(fixture.action(cid,3,'close').status_code,409)
            self.assertEqual(fixture.client.get('/api/farm/follow-ups/'+cid+'/events',headers=fixture.headers[0]).json['items'][0],frozen)
        finally:
            fixture.doCleanups()


if __name__ == '__main__':
    unittest.main()
