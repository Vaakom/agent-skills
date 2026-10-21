"""Experimental per-recording agreement between browser hints and local voice turns.
Never repairs uncertain voice labels or propagates a name without a current browser hint.
"""
import json
import math
from bisect import bisect_left, bisect_right
from collections import defaultdict, Counter
from pathlib import Path

def overlap(a, b, c, d):
    return max(0.0, min(b, d) - max(a, c))

def duration(intervals):
    total = 0.0
    end = -1.0
    for a, b in sorted(intervals):
        total += max(0.0, b - max(a, end))
        end = max(end, b)
    return total

def load_spans(path):
    samples = [json.loads(line) for line in path.read_text('utf-8').splitlines()]
    previous = -1.0
    profiles = set()
    for s in samples:
        if not isinstance(s, dict):
            raise ValueError('Invalid journal entry')
        t, names = s.get('seconds'), s.get('speakers')
        if (not isinstance(t, (int, float)) or not math.isfinite(t) or t < 0 or t <= previous
            or not isinstance(names, list) or len(names) > 30
            or any(not isinstance(n, str) or not n.strip() or len(n) > 160 for n in names)
            or not isinstance(s.get('profile'), str)):
            raise ValueError('Invalid or out-of-order journal')
        previous = t
        profiles.add(s['profile'])
    if len(profiles) > 1:
        raise ValueError('Profile changed during recording; retain voice labels')
    profile = json.loads(next(iter(profiles), '{}'))
    if not isinstance(profile, dict) or profile.get('algorithm') != 'browser_voice_agreement_v2':
        return []
    spans = []
    for a, b in zip(samples, samples[1:]):
        if not (0 < b['seconds'] - a['seconds'] <= 1.0):
            continue
        if not all(s.get('calibrated') is True and s.get('state') == 'observing' for s in (a, b)):
            continue
        if len(a['speakers']) != 1 or a['speakers'] != b['speakers']:
            continue
        start, end, name = a['seconds'], b['seconds'], a['speakers'][0]
        if spans and spans[-1][2] == name and abs(spans[-1][1] - start) < .001:
            spans[-1] = (spans[-1][0], end, name)
        else:
            spans.append((start, end, name))
    # Conservative transition guard; its real accuracy still needs audio validation.
    return [(a + .4, b - .4, name) for a, b, name in spans if b - a >= 1.8]

def apply_names(rows, session, turns=None):
    path = Path(session) / 'browser-speakers.jsonl'
    if not path.exists():
        return rows
    report = {'schema': 2, 'method': 'browser_voice_agreement', 'state': 'insufficient_evidence',
              'thresholds': {'support_seconds': 3, 'separate_intervals': 2, 'agreement': .90},
              'mappings': {}, 'rejections': {}, 'named_words': 0,
              'limitation': 'Undetected acoustic overlap and clustering errors can still cause incorrect names; review required.'}
    def finish(result):
        (Path(session) / 'speaker-name-report.json').write_text(
            json.dumps(report, ensure_ascii=False, indent=2), 'utf-8')
        return result
    try:
        spans = load_spans(path)
    except (ValueError, OSError, TypeError) as exc:
        report.update(state='invalid_journal', reason=str(exc))
        return finish(rows)
    if not turns:
        report['state'] = 'missing_voice_turns'
        return finish(rows)
    ordered = sorted(turns, key=lambda t: (t['start'], t['end']))
    starts = [t['start'] for t in ordered]
    ends = []
    for t in ordered:
        ends.append(max(t['end'], ends[-1] if ends else 0))
    labels = {}
    for turn in ordered:
        if turn['speaker'] not in labels:
            labels[turn['speaker']] = 'Спикер ' + str(len(labels) + 1)
    own = [(r['start'] - .2, r['end'] + .2) for r in rows if r['speaker'] == 'Я']
    rejected = Counter()
    candidates = {}
    votes = defaultdict(list)
    bursts = defaultdict(set)
    for index, row in enumerate(rows):
        label = row['speaker']
        if label == 'Я':
            continue
        a, b = row['start'], row['end']
        length = b - a
        ev = row.get('speaker_evidence', {})
        if (length <= 0 or label not in labels.values()
            or ev.get('method') != 'local_voice_clustering' or ev.get('status') != 'assigned'
            or ev.get('coverage', 0) < .90 or ev.get('overlap', 1) > 0):
            rejected['uncertain_voice'] += 1
            continue
        if any(overlap(a, b, c, d) > 0 for c, d in own):
            rejected['own_microphone_overlap'] += 1
            continue
        active = [t for t in ordered[bisect_right(ends, a):bisect_left(starts, b)]
                  if overlap(a, b, t['start'], t['end']) > 0]
        if (len({t['speaker'] for t in active}) != 1 or
            any(labels[t['speaker']] != label for t in active) or
            duration([(max(a, t['start']), min(b, t['end'])) for t in active]) / length < .90):
            rejected['voice_turn_overlap_or_gap'] += 1
            continue
        scores = defaultdict(float)
        evidence = defaultdict(set)
        for j, (c, d, name) in enumerate(spans):
            value = overlap(a, b, c, d)
            if value:
                scores[name] += value
                evidence[name].add(j)
        ranked = sorted(scores, key=scores.get, reverse=True)
        if not ranked or scores[ranked[0]] / length < .80 or len(ranked) != 1:
            rejected['browser_gap_or_ambiguity'] += 1
            continue
        name = ranked[0]
        candidates[index] = (label, name, min(1.0, scores[name] / length))
        # Union prevents duplicated word intervals from manufacturing support.
        votes[label, name].append((a, b))
        bursts[label, name].update(evidence[name])
    mappings = {}
    support = {}
    for label in {key[0] for key in votes}:
        choices = {name: duration(times) for (voice, name), times in votes.items() if voice == label}
        name = max(choices, key=choices.get)
        seconds, total = choices[name], sum(choices.values())
        if seconds + 1e-6 >= 3 and len(bursts[label, name]) >= 2 and seconds / total >= .90:
            mappings[label] = name
            support[label] = {'seconds': round(seconds, 3), 'intervals': len(bursts[label, name]),
                              'agreement': round(seconds / total, 3)}
    # A name associated with multiple voice clusters is ambiguous in this implementation.
    counts = Counter(mappings.values())
    mappings = {voice: name for voice, name in mappings.items() if counts[name] == 1}
    result = []
    for index, row in enumerate(rows):
        candidate = candidates.get(index)
        if candidate and mappings.get(candidate[0]) == candidate[1]:
            voice, name, coverage = candidate
            result.append({**row, 'speaker': name, 'speaker_evidence': {
                'method': 'browser_voice_agreement', 'status': 'experimental',
                'previous_label': voice, 'browser_coverage': round(coverage, 3),
                'voice': row['speaker_evidence'], 'mapping_support': support[voice]}})
            report['named_words'] += 1
        else:
            result.append(row)
    report.update(state='applied' if report['named_words'] else 'insufficient_evidence',
                  mappings={v: {'name': n, **support[v]} for v, n in mappings.items()},
                  rejections=dict(rejected))
    return finish(result)
