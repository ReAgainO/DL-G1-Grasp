"""Positive/negative source resolver tests; no MuJoCo import or stepping."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from motion_profile import MotionProfile, ROLES, sha


class ProfileTests(unittest.TestCase):
    def setUp(self):
        # A known workspace directory avoids the Windows sandbox's alternate
        # system TEMP ACL. Cleanup is confined to this newly allocated child.
        workspace = Path(__file__).resolve().parent
        self.temp = tempfile.TemporaryDirectory(dir=workspace, prefix='profile-test-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        assert self.root.is_relative_to(workspace) and self.root != workspace
        self.spec = dict(schema_version=1, generation_summary='generation.json', roles={})
        jobs = []
        for index, role in enumerate(ROLES):
            for suffix in ['npz', 'csv']:
                (self.root/f'{role}.{suffix}').write_bytes((role+suffix).encode())
            self.spec['roles'][role] = dict(npz=role+'.npz', csv=role+'.csv',
                npz_sha256=sha(self.root/(role+'.npz')), csv_sha256=sha(self.root/(role+'.csv')),
                generation_job=role)
            jobs.append(dict(stem=role, seed=index+42, prompt=role+' text', num_frames=100, wall_s=3.))
        self.summary = dict(fps=25, skeleton_cls='G1Skeleton34', jobs=jobs)
        self.save_summary()
        self.save()

    def save_summary(self):
        (self.root/'generation.json').write_text(json.dumps(self.summary))
        self.spec['generation_summary_sha256'] = sha(self.root/'generation.json')

    def save(self):
        (self.root/'profile.json').write_text(json.dumps(self.spec))

    def load(self):
        self.save()
        return MotionProfile(self.root, 'profile.json')

    def test_verified_roles(self):
        profile = self.load()
        entry = profile.entries['reach']
        motion = SimpleNamespace(text='reach text', audit=dict(source_npz_sha256=entry['npz_sha256'],
            paired_csv_sha256=entry['csv_sha256'], source_fps=25, native_frames=100))
        profile.validate_motion('reach', motion)
        self.assertEqual(profile.audit()['roles']['reach']['seed_from_generation_summary'], 42)
        self.assertFalse(profile.audit()['semantic_completion_validated'])

    def test_reject_changed_npz(self):
        (self.root/'reach.npz').write_bytes(b'changed')
        with self.assertRaises(ValueError): self.load()

    def test_reject_changed_csv(self):
        (self.root/'reach.csv').write_bytes(b'changed')
        with self.assertRaises(ValueError): self.load()

    def test_reject_changed_generation_summary(self):
        (self.root/'generation.json').write_text('{}')
        with self.assertRaises(ValueError): self.load()

    def test_reject_missing_role(self):
        del self.spec['roles']['hold']
        with self.assertRaises(ValueError): self.load()

    def test_reject_extra_role(self):
        self.spec['roles']['extra'] = copy.deepcopy(self.spec['roles']['reach'])
        with self.assertRaises(ValueError): self.load()

    def test_reject_traversal(self):
        self.spec['roles']['reach']['npz'] = '../reach.npz'
        with self.assertRaises(ValueError): self.load()

    def test_reject_absolute(self):
        self.spec['roles']['reach']['npz'] = str(self.root/'reach.npz')
        with self.assertRaises(ValueError): self.load()

    def test_reject_wrong_job(self):
        self.spec['roles']['reach']['generation_job'] = 'hold'
        with self.assertRaises(ValueError): self.load()

    def test_reject_duplicate_job(self):
        self.summary['jobs'].append(copy.deepcopy(self.summary['jobs'][0]))
        self.save_summary()
        with self.assertRaises(ValueError): self.load()

    def test_reject_fps(self):
        self.summary['fps'] = 30
        self.save_summary()
        with self.assertRaises(ValueError): self.load()

    def test_reject_seed(self):
        self.summary['jobs'][0]['seed'] = -1
        self.save_summary()
        with self.assertRaises(ValueError): self.load()

    def test_reject_frame_count(self):
        self.summary['jobs'][0]['num_frames'] = 2251
        self.save_summary()
        with self.assertRaises(ValueError): self.load()

    def test_reject_text_mismatch(self):
        profile = self.load()
        entry = profile.entries['reach']
        motion = SimpleNamespace(text='different', audit=dict(source_npz_sha256=entry['npz_sha256'],
            paired_csv_sha256=entry['csv_sha256'], source_fps=25, native_frames=100))
        with self.assertRaises(ValueError): profile.validate_motion('reach', motion)

    def test_reject_duplicate_json_key(self):
        (self.root/'profile.json').write_text('{"schema_version":1,"schema_version":1}')
        with self.assertRaises(ValueError): MotionProfile(self.root, 'profile.json')


if __name__ == '__main__':
    unittest.main(verbosity=2)
