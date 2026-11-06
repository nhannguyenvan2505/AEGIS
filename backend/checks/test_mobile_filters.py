"""H2-T01: one state filter, before pagination, synthetic owned stores only."""
from datetime import timedelta
from pathlib import Path
import sys,threading,unittest,uuid
BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND));sys.path.insert(0,str(BACKEND.parent/'frontend'))
from pilot_app import create_pilot_app
from pilot_backup import inventory
import test_followup

class MobileFilterTests(unittest.TestCase):
    def setUp(self):
        f=test_followup.FollowupTests('test_full_lifecycle_retry_reopen_and_no_disease_label')
        self.addCleanup(f.doCleanups);f.setUp();self.f=f
        f.app=create_pilot_app(f.root,'http://127.0.0.1:9');f.app.config['FARM_WRITE_LIMIT']=500
        f.client=f.app.test_client();self.url='/api/farm/seasons/'+f.season['id']+'/follow-ups'
        self.states={s:[] for s in ['open','acknowledged','checked','closed']}
        for i,state in enumerate(['checked','open','closed','acknowledged','open','checked']):
            r=f.client.post('/api/farm/devices/'+f.device+'/assessments',headers=f.headers[0],
                json={'as_of':(test_followup.END-timedelta(hours=24+i)).isoformat()})
            self.assertEqual(r.status_code,201);a=r.json['item']
            self.assertEqual(a['result']['status'],'insufficient_data')
            r=f.client.post('/api/farm/assessments/'+a['id']+'/follow-up',headers=f.headers[0],json={'reason':'Synthetic filter fixture'})
            self.assertEqual(r.status_code,201);cid=r.json['item']['id']
            actions={'open':[],'acknowledged':['acknowledge'],'checked':['acknowledge','check'],
                     'closed':['acknowledge','check','close']}[state]
            for version,action in enumerate(actions,1):
                self.assertEqual(f.command(cid,version,action,observation_id=None)[0].status_code,201)
            self.states[state].append(cid)

    def get(self,query='',headers=None):
        return self.f.client.get(self.url+query,headers=self.f.headers[0] if headers is None else headers)

    def test_each_state_and_unfiltered_legacy_order(self):
        all_items=self.get().json['items']
        self.assertEqual(len(all_items),6)
        self.assertEqual([r['id'] for r in all_items],sorted([r['id'] for r in all_items],reverse=True))
        for state,ids in self.states.items():
            r=self.get('?state='+state);self.assertEqual(r.status_code,200)
            self.assertEqual([x['id'] for x in r.json['items']],[x['id'] for x in all_items if x['state']==state])
            self.assertEqual(set(x['id'] for x in r.json['items']),set(ids))
            self.assertEqual(r.json['pagination']['total'],len(ids))
        self.assertEqual(self.get().json['items'],all_items)

    def test_filter_before_pagination_counts_and_out_of_range(self):
        expected=self.get('?state=checked').json['items']
        found=[]
        for page in [1,2,3]:
            r=self.get(f'?state=checked&page={page}&page_size=1');self.assertEqual(r.status_code,200)
            p=r.json['pagination'];self.assertEqual(p,dict(page=page,page_size=1,total=2,total_pages=2,has_next=page<2))
            found+=r.json['items']
        self.assertEqual(found,expected)

    def test_invalid_empty_duplicate_and_unknown_query(self):
        for value in ['', 'OPEN','all','open,checked','%20open','open%20',"open%27%20OR%201=1--",'kh%E1%BB%8Fe']:
            with self.subTest(value=value):
                r=self.get('?state='+value);self.assertEqual(r.status_code,400)
                self.assertEqual(r.json['error']['code'],'invalid_followup_filter')
                self.assertEqual(r.json['request_id'],r.headers['X-Request-ID'])
        for query in ['?state=open&state=open','?state=open&state=closed']:
            r=self.get(query);self.assertEqual(r.status_code,400);self.assertEqual(r.json['error']['code'],'invalid_followup_filter')
        for query in ['?state=open&task_kind=check_data','?device=x','?state=open&page=0','?state=open&page=1&page=2','?state=open&page_size=101']:
            r=self.get(query);self.assertEqual(r.status_code,400);self.assertEqual(r.json['error']['code'],'invalid_pagination')

    def test_owner_season_empty_and_auth_boundaries(self):
        self.assertEqual(self.get('?state=checked',headers={}).status_code,401)
        for query in ['?state=checked','?state=INVALID']:
            r=self.get(query,headers=self.f.headers[1]);self.assertEqual(r.status_code,404);self.assertNotIn('items',r.json)
        missing='/api/farm/seasons/'+str(uuid.uuid4())+'/follow-ups?state=open'
        self.assertEqual(self.f.client.get(missing,headers=self.f.headers[0]).status_code,404)
        # No closed case matches after reopening the only closed item.
        cid=self.states['closed'][0]
        self.assertEqual(self.f.command(cid,4,'reopen')[0].status_code,201)
        r=self.get('?state=closed');self.assertEqual(r.json['items'],[])
        self.assertEqual(r.json['pagination'],dict(page=1,page_size=20,total=0,total_pages=0,has_next=False))
        self.assertEqual(self.get('?state=acknowledged').json['pagination']['total'],2)
        # Another owned season must not inherit this season's matching cases.
        r=self.f.client.post('/api/farm/plots/'+self.f.season['plot_id']+'/seasons',headers=self.f.headers[0],
            json=dict(name='Other filter season',start_date='2027-01-01',end_date='2027-03-01'))
        self.assertEqual(r.status_code,201)
        url='/api/farm/seasons/'+r.json['item']['id']+'/follow-ups?state=open'
        r=self.f.client.get(url,headers=self.f.headers[0]);self.assertEqual(r.status_code,200)
        self.assertEqual(r.json['items'],[]);self.assertEqual(r.json['pagination']['total'],0)

    def test_read_only_and_other_routes_still_reject_state(self):
        before=inventory(self.f.root)
        r=self.get('?state=open');self.assertEqual(r.status_code,200)
        self.assertEqual(r.headers['Cache-Control'],'private, no-store');self.assertIn('Authorization',r.headers['Vary'])
        self.assertEqual(inventory(self.f.root),before)
        cid=self.states['open'][0]
        for path in ['/api/farm/plots?state=open','/api/farm/follow-ups/'+cid+'/events?state=open']:
            r=self.f.client.get(path,headers=self.f.headers[0]);self.assertEqual(r.status_code,400)
            self.assertEqual(r.json['error']['code'],'invalid_pagination')

    def test_real_http_filtered_pagination(self):
        import requests
        from werkzeug.serving import make_server
        server=make_server('127.0.0.1',0,self.f.app,threaded=True)
        worker=threading.Thread(target=server.serve_forever);worker.start()
        try:
            with requests.Session() as session:
                session.trust_env=False
                r=session.get('http://127.0.0.1:'+str(server.server_port)+self.url,
                    params=dict(state='checked',page=2,page_size=1),headers=self.f.headers[0],timeout=10)
                self.assertEqual(r.status_code,200);self.assertEqual(r.json()['pagination']['total'],2)
                self.assertEqual(len(r.json()['items']),1);self.assertEqual(r.json()['items'][0]['state'],'checked')
        finally:server.shutdown();server.server_close();worker.join(10)
        self.assertFalse(worker.is_alive())

if __name__=='__main__':unittest.main()
