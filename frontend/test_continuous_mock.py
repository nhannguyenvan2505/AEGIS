from datetime import datetime,timedelta,timezone
import os,unittest
from continuous_mock import Generator,hour,process_resources,worker_pid

EPOCH=datetime(2026,10,25,10,tzinfo=timezone.utc)


class ContinuousTests(unittest.TestCase):
    def test_only_completed_buckets_and_acknowledged_state(self):
        g=Generator(EPOCH);at=EPOCH+timedelta(minutes=59)
        rows=g.pending('a','continuous',at);self.assertEqual(len(rows),24);self.assertEqual(rows[-1]['start_at'],(EPOCH-timedelta(hours=1)).isoformat())
        self.assertTrue(all(datetime.fromisoformat(r['start_at'])<hour(at) for r in rows))
        self.assertEqual(g.pending('a','continuous',at),rows);g.acknowledge('a',rows);self.assertEqual(g.pending('a','continuous',at),[])
        next_rows=g.pending('a','continuous',EPOCH+timedelta(hours=1));self.assertEqual([r['start_at'] for r in next_rows],[EPOCH.isoformat()])

    def test_late_source_has_explicit_real_delay(self):
        g=Generator(EPOCH,12);rows=g.pending('a','late',EPOCH+timedelta(hours=1,seconds=11));self.assertEqual(len(rows),23)
        g.acknowledge('a',rows);rows=g.pending('a','late',EPOCH+timedelta(hours=1,seconds=12));self.assertEqual([r['start_at'] for r in rows],[EPOCH.isoformat()])

    def test_gaps_are_intentional_and_never_backfilled(self):
        g=Generator(EPOCH);rows=g.pending('i','intermittent',EPOCH+timedelta(hours=3));self.assertNotIn((EPOCH+timedelta(hours=1)).isoformat(),[r['start_at'] for r in rows]);self.assertNotIn((EPOCH+timedelta(hours=2)).isoformat(),[r['start_at'] for r in rows])
        g.acknowledge('i',rows);later=g.pending('i','intermittent',EPOCH+timedelta(hours=4));self.assertEqual([r['start_at'] for r in later],[(EPOCH+timedelta(hours=3)).isoformat()])

    def test_outage_recovery_and_pause_schedule(self):
        g=Generator(EPOCH);rows=g.pending('o','outage',EPOCH+timedelta(hours=4));stamps=[r['start_at'] for r in rows]
        for h in [0,1,2]:self.assertNotIn((EPOCH+timedelta(hours=h)).isoformat(),stamps)
        self.assertIn((EPOCH+timedelta(hours=3)).isoformat(),stamps)
        for h,enabled in [(0,True),(2,False),(3,False),(4,True),(10,False)]:self.assertEqual(g.enabled('paused',EPOCH+timedelta(hours=h)),enabled)
        self.assertTrue(g.enabled('continuous',EPOCH+timedelta(hours=2)))

    def test_restart_backend_keeps_cursor_and_payload_deterministic(self):
        g=Generator(EPOCH);rows=g.pending('a','continuous',EPOCH);g.acknowledge('a',rows)
        self.assertEqual(g.pending('a','continuous',EPOCH),[]);self.assertEqual(g.pending('b','continuous',EPOCH),rows)
        self.assertEqual(g.state()['epoch'],EPOCH.isoformat());self.assertEqual(len(g.state()['sent']['a']),24)

    def test_state_bounded_and_catchup_not_all_history(self):
        g=Generator(EPOCH)
        for h in range(72):
            rows=g.pending('a','continuous',EPOCH+timedelta(hours=h));self.assertLessEqual(len(rows),24);g.acknowledge('a',rows)
        self.assertLessEqual(len(g.state()['sent']['a']),49)

    @unittest.skipUnless(os.name=='nt','Windows native metrics')
    def test_resources_target_current_interpreter(self):
        sample=process_resources(os.getpid());self.assertTrue(sample['supported']);self.assertGreater(sample['private_bytes'],0);self.assertGreater(sample['handle_count'],0);self.assertEqual(worker_pid(os.getpid()),os.getpid())


if __name__=='__main__':unittest.main()
