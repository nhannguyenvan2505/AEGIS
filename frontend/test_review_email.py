"""Known exact email can designate a reviewer without a public account directory."""
import unittest
import uuid
import test_journal


class ReviewEmailTests(unittest.TestCase):
    setUp=test_journal.JournalTests.setUp

    def grant_payload(self,**changes):
        p=dict(client_grant_id=str(uuid.uuid4()),reviewer_email=' JOURNAL-OTHER@example.test ',reviewer_alias='Synthetic reviewer',
               qualification_reference='Unverified',scope='assigned_observations_and_images',reason='Known email synthetic invitation')
        p.update(changes);return p

    def post(self,p,owner=0):
        return self.client.post('/api/farm/seasons/'+self.season['id']+'/review-grants',json=p,headers=self.headers[owner] if owner is not None else {})

    def test_exact_normalized_email_preserves_consent_and_idempotency(self):
        p=self.grant_payload();r=self.post(p);self.assertEqual(r.status_code,201);grant=r.json['item']
        self.assertEqual(grant['state'],'offered');self.assertFalse(grant['training_approved'])
        reviewer=self.client.get('/api/auth/me',headers=self.headers[1]).json['user']['id']
        self.assertEqual(grant['metadata']['reviewer_id'],reviewer)
        self.assertEqual(self.post(p).status_code,200)
        self.assertEqual(self.post(dict(p,reviewer_email='different@example.test')).status_code,409)
        self.assertEqual(self.client.get('/api/farm/review-inbox',headers=self.headers[1]).json['items'][0]['id'],grant['id'])

    def test_exactly_one_identifier_and_valid_email_required(self):
        missing=self.grant_payload();missing.pop('reviewer_email')
        for p in [missing,self.grant_payload(reviewer_id=str(uuid.uuid4())),self.grant_payload(reviewer_email='not-an-email'),self.grant_payload(reviewer_email=None),self.grant_payload(reviewer_email='x'*255+'@a.test')]:
            with self.subTest(p=p):self.assertEqual(self.post(p).status_code,400)

    def test_owner_auth_scope_self_and_missing_account_stay_guarded(self):
        self.assertEqual(self.post(self.grant_payload(),None).status_code,401)
        self.assertEqual(self.post(self.grant_payload(),1).status_code,404)
        self.assertEqual(self.post(self.grant_payload(reviewer_email='missing@example.test')).status_code,404)
        self.assertEqual(self.post(self.grant_payload(reviewer_email='journal-owner@example.test')).status_code,400)
        self.assertEqual(self.post(self.grant_payload(scope='all_owner_images')).status_code,400)
        self.app.config['FARM_WRITE_LIMIT']=1
        r=self.post(self.grant_payload());self.assertEqual(r.status_code,429);self.assertIn('Retry-After',r.headers)


if __name__=='__main__':unittest.main()
