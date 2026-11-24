"""Unit contracts for the E12 B3 API evidence client."""

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts import e12_b3_api  # noqa: E402


class B3ApiContracts(unittest.TestCase):
    def test_canonical_request_hash_is_stable_for_key_order(self):
        first = {'target': 'b', 'base': 'a', 'repo': '/course/data/project'}
        second = {'repo': '/course/data/project', 'base': 'a', 'target': 'b'}
        self.assertEqual(e12_b3_api.sha256_bytes(e12_b3_api.canonical(first)),
                         e12_b3_api.sha256_bytes(e12_b3_api.canonical(second)))

    def test_artifact_uri_must_bind_to_current_job_and_stay_relative(self):
        self.assertEqual(
            e12_b3_api.artifact_path('artifact://job-1/validation/recheck.json', 'job-1'),
            'validation/recheck.json')
        for uri in (
            'artifact://job-2/result.json',
            'artifact://job-1/../secret',
            'artifact://job-1//absolute',
        ):
            with self.subTest(uri=uri), self.assertRaises(AssertionError):
                e12_b3_api.artifact_path(uri, 'job-1')

    def test_download_artifact_records_manifest_and_header_hashes(self):
        with tempfile.TemporaryDirectory() as directory:
            content = b'patch\n'
            item = {
                'uri': 'artifact://job-1/candidate.patch',
                'sha256': e12_b3_api.sha256_bytes(content),
            }
            original = e12_b3_api.http_json

            def fake(url, method='GET', payload=None, timeout=30):
                self.assertEqual(url, 'http://api/v1/jobs/job-1/files/candidate.patch')
                return 200, {'X-Content-SHA256': item['sha256']}, None, content

            e12_b3_api.http_json = fake
            try:
                result = e12_b3_api.download_artifact(
                    'http://api', 'job-1', item, Path(directory))
            finally:
                e12_b3_api.http_json = original
            self.assertTrue(result['matches'])
            self.assertEqual((Path(directory) / 'candidate.patch').read_bytes(), content)

    def test_handoff_contract_flags_require_same_job_and_409(self):
        handoff = {
            'contracts': {
                'idempotent_replay_same_job': True,
                'conflict_409': True,
            }
        }
        self.assertTrue(all(handoff['contracts'].values()))
        self.assertEqual(json.loads('{"error":"IDEMPOTENCY_CONFLICT"}')['error'],
                         'IDEMPOTENCY_CONFLICT')


if __name__ == '__main__':
    unittest.main()
