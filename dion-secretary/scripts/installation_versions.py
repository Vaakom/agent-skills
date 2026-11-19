"""Read-only comparison of source versions with recently observed runtime evidence."""
import json
from pathlib import Path
import time

SECRETARY_VERSION = '2.3.0'
EXPECTED_PROTOCOL = 1


def versions_report(config, root, now=None):
    now = time.time() if now is None else now
    expected = None
    path = config.get('speaker_helper_extension_path')
    if path:
        try:
            expected = json.loads((Path(path) / 'manifest.json').read_text('utf-8'))['version']
        except (OSError, ValueError, KeyError):
            pass
    observed = []
    for meta_path in Path(root).glob('*/*/meta.json'):
        try:
            m = json.loads(meta_path.read_text('utf-8'))
            age = now - m['last_at']
            if not 0 <= age <= 5 or m.get('ended_at', 0) >= m['last_at']:
                continue
            v = m.get('versions', {})
            active = v.get('extension')
            observed.append(dict(tab=m.get('tab'), extension=active or 'unknown', host=v.get('host', 'unknown'),
                protocol=v.get('protocol'), compatible=(v['protocol'] == EXPECTED_PROTOCOL if 'protocol' in v else None),
                reload_required=(active != expected if active not in (None, 'unknown') and expected else None),
                age_seconds=round(age, 2)))
        except (OSError, ValueError, KeyError, TypeError):
            continue
    return dict(secretary=SECRETARY_VERSION, expected_protocol=EXPECTED_PROTOCOL,
                installed_extension_manifest=expected, active_observations=observed,
                state='observed' if observed else 'unknown',
                note='Source/installed files alone do not prove the active Chrome or host version. Refresh/reload may be needed; missing evidence is unknown.')
