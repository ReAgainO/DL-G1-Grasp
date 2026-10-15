"""Bounded, immutable source manifest for already generated ARDY clips.

This resolves sources, not a motion planner or a generation-success claim.
Seed and generation timing are attributed to the verified generation summary,
not inferred from an NPZ that may not embed them.
"""
import hashlib
import json
from pathlib import Path

ROLES = ('reach', 'lift', 'hold', 'release')


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024**2), b''):
            digest.update(block)
    return digest.hexdigest()


def bounded_path(root, relative, suffix, limit):
    if not isinstance(relative, str) or not relative or len(relative) > 512:
        raise ValueError('Bounded relative path required')
    path = Path(relative)
    if path.is_absolute() or '..' in path.parts or path.suffix != suffix:
        raise ValueError('Relative path/type contract failed')
    resolved = (root / path).resolve()
    if not resolved.is_relative_to(root) or not resolved.is_file():
        raise ValueError('Source missing or escapes project evidence root')
    if not 0 < resolved.stat().st_size <= limit:
        raise ValueError('Source size bound failed')
    return resolved


def read_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('Duplicate JSON key')
            result[key] = value
        return result
    return json.loads(path.read_text(), object_pairs_hook=unique)


class MotionProfile:
    def __init__(self, root, relative):
        self.root = Path(root).resolve()
        self.path = bounded_path(self.root, relative, '.json', 64*1024)
        spec = read_json(self.path)
        if (not isinstance(spec, dict) or spec.get('schema_version') != 1
                or not isinstance(spec.get('roles'), dict) or set(spec['roles']) != set(ROLES)):
            raise ValueError('Profile needs schema1 and exactly four roles')
        self.summary = bounded_path(self.root, spec['generation_summary'], '.json', 256*1024)
        self.summary_sha = sha(self.summary)
        if self.summary_sha != spec['generation_summary_sha256']:
            raise ValueError('Generation summary SHA mismatch')
        summary = read_json(self.summary)
        if not isinstance(summary, dict) or summary.get('fps') != 25 or summary.get('skeleton_cls') != 'G1Skeleton34':
            raise ValueError('Generation skeleton/fps mismatch')
        jobs = summary.get('jobs', [])
        if (not isinstance(jobs, list) or not 1 <= len(jobs) <= 20
                or not all(isinstance(j, dict) and isinstance(j.get('stem'), str) for j in jobs)
                or len({j['stem'] for j in jobs}) != len(jobs)):
            raise ValueError('Generation jobs must be unique and bounded')
        self.entries = {}
        for role in ROLES:
            entry = spec['roles'][role]
            if not isinstance(entry, dict):
                raise ValueError('Role source record required')
            npz = bounded_path(self.root, entry['npz'], '.npz', 100*1024**2)
            csv = bounded_path(self.root, entry['csv'], '.csv', 8*1024**2)
            if npz.stem != csv.stem or npz.stem != entry['generation_job']:
                raise ValueError('NPZ/CSV/generation-job stem mismatch')
            if sha(npz) != entry['npz_sha256'] or sha(csv) != entry['csv_sha256']:
                raise ValueError('Source SHA mismatch')
            matches = [j for j in jobs if j['stem'] == entry['generation_job']]
            if len(matches) != 1:
                raise ValueError('Missing generation job')
            job = matches[0]
            if (type(job.get('seed')) is not int or not 0 <= job['seed'] < 2**32
                    or not isinstance(job.get('prompt'), str) or not 1 <= len(job['prompt']) <= 4096
                    or type(job.get('num_frames')) is not int or not 2 <= job['num_frames'] <= 2250):
                raise ValueError('Generation job seed/text/frame contract failed')
            self.entries[role] = dict(npz=npz, csv=csv, job=job,
                npz_sha256=entry['npz_sha256'], csv_sha256=entry['csv_sha256'])
        if (len({e['npz'] for e in self.entries.values()}) != len(ROLES)
                or len({e['npz'].stem for e in self.entries.values()}) != len(ROLES)):
            raise ValueError('Distinct role inputs required; role labels are not semantic certification')
        self.observed = {}

    def validate_motion(self, role, motion):
        entry = self.entries[role]
        audit = motion.audit
        if (audit['source_npz_sha256'] != entry['npz_sha256']
                or audit.get('paired_csv_sha256') != entry['csv_sha256']
                or audit['source_fps'] != 25 or audit['native_frames'] != entry['job']['num_frames']
                or motion.text != entry['job']['prompt']):
            raise ValueError('Converted NPZ does not match verified generation job')
        self.observed[role] = dict(stem=entry['npz'].stem,
            source_npz=str(entry['npz']), source_npz_sha256=entry['npz_sha256'],
            paired_csv_sha256=entry['csv_sha256'], text=motion.text,
            seed_from_generation_summary=entry['job']['seed'],
            generation_job_wall_s=entry['job'].get('wall_s'),
            text_encode_s=entry['job'].get('text_encode_s'),
            interpretation='Verified input identity; seed from generation record, not NPZ inference; no grasp success or full-pipeline latency assertion')

    def audit(self):
        return dict(profile_path=str(self.path), profile_sha256=sha(self.path),
            generation_summary=str(self.summary), generation_summary_sha256=self.summary_sha,
            roles=self.observed.copy(), human_correction=False,
            semantic_completion_validated=False,
            role_definition='Explicit source-role mapping, not proof that generated motion grasps, holds or places an object')
