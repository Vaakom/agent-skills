"""Pure recording health calculations; no devices, models or services are opened."""
import json
from pathlib import Path
import wave


class AudioHealth:
    def __init__(self, started, stall_seconds=5.0):
        self.started = started
        self.stall_seconds = stall_seconds
        self.tracks = {}

    def register(self, label, rate, channels):
        self.tracks[label] = dict(rate=rate, channels=channels, frames=0, first_at=None, last_at=None)

    def received(self, label, byte_count, now):
        track = self.tracks[label]
        frames = byte_count // (2 * track['channels'])
        if frames:
            track['frames'] += frames
            if track['first_at'] is None:
                track['first_at'] = now - frames / track['rate']
            track['last_at'] = now

    def snapshot(self, now):
        result = {}
        for label, t in self.tracks.items():
            age = now - (t['last_at'] if t['last_at'] is not None else self.started)
            expected = max(0, now - t['first_at']) if t['first_at'] is not None else 0
            seconds = t['frames'] / t['rate']
            missing = max(0, expected - seconds)
            state = ('no_data' if not t['frames'] else 'stalled') if age >= self.stall_seconds else ('receiving' if t['frames'] else 'waiting')
            if state == 'receiving' and missing > max(5, expected * .05):
                state = 'duration_gap'
            result[label] = dict(state=state, frames=t['frames'], audio_seconds=round(seconds, 3),
                                 expected_seconds=round(expected, 3), missing_seconds=round(missing, 3),
                                 last_buffer_age_seconds=round(max(0, age), 3))
        return result


def inspect_wavs(session, elapsed_seconds, live_tracks=None):
    """Read finalized headers, retaining a problem for each absent/broken track."""
    tracks = {}
    for label in ('remote', 'microphone'):
        path = Path(session) / (label + '.wav')
        if not path.exists():
            tracks[label] = {'state': 'absent'}
            continue
        try:
            with wave.open(str(path), 'rb') as wav:
                frames, rate = wav.getnframes(), wav.getframerate()
                duration = frames / rate
            measured = (live_tracks or {}).get(label)
            expected = measured['expected_seconds'] if measured else elapsed_seconds
            # No buffers is a failure even for a very short session.
            gap = max(0, expected - duration)
            state = 'empty' if not frames else ('short' if gap > max(5, expected * .05) else 'available')
            tracks[label] = dict(state=state, frames=frames, audio_seconds=round(duration, 3),
                                 expected_seconds=round(expected, 3), missing_seconds=round(gap, 3))
        except (OSError, EOFError, wave.Error, ZeroDivisionError) as exc:
            tracks[label] = dict(state='unreadable', error=str(exc))
    return dict(schema=1, elapsed_seconds=round(elapsed_seconds, 3), tracks=tracks,
                complete_remote=tracks['remote']['state'] == 'available',
                note='Available duration is not proof that all meeting speech was captured.')


def journal_diagnostic(binding):
    if not binding:
        return {'state': 'unbound', 'coverage': 'unknown'}
    try:
        state = json.loads(Path(binding['lifecycle_path']).read_text('utf-8'))
        matches = all(state.get(key) == binding.get(key) for key in ('client', 'tab', 'meeting_id'))
        return dict(state='matching' if matches else 'mismatch', lifecycle_state=state.get('state'),
                    coverage='unknown')
    except (OSError, ValueError, KeyError) as exc:
        return dict(state='unavailable', coverage='unknown', error=str(exc))


def sample_coverage(events, origin, length):
    """Conservative intervals between adjacent fresh samples; never fill long gaps."""
    valid = sorted((e for e in events if isinstance(e.get('monotonic'), (int, float))
                    and origin <= e['monotonic'] <= origin + length), key=lambda e: e['monotonic'])
    # Reconnect duplicates must not manufacture duration.
    valid = list({e['monotonic']: e for e in valid}.values())
    observed = named = 0.0
    for a, b in zip(valid, valid[1:]):
        delta = b['monotonic'] - a['monotonic']
        if 0 < delta <= 1.5:
            observed += delta
            if a.get('state') == 'observing' and a.get('speakers'):
                named += delta
    return dict(coverage='estimated', observed_seconds=round(observed, 3),
                named_indicator_seconds=round(named, 3), audio_seconds=round(length, 3),
                observed_fraction=round(observed / length, 4) if length else None,
                samples=len(valid), note='UI observations only; silence is not missing names and indicators are not verified identities.')


def inspect_journal(session, root, binding, boot_epoch):
    result = journal_diagnostic(binding)
    if not binding:
        return result
    try:
        origin = json.loads((Path(session) / 'recording_clock.json').read_text('utf-8'))['remote_monotonic']
        with wave.open(str(Path(session) / 'remote.wav'), 'rb') as wav:
            length = wav.getnframes() / wav.getframerate()
        events = []
        for meta_path in Path(root).glob('*/*/meta.json'):
            try:
                meta = json.loads(meta_path.read_text('utf-8'))
                if not all(meta.get(k) == binding.get(k) for k in ('client', 'tab', 'meeting_id')):
                    continue
                if abs(meta['boot_epoch'] - boot_epoch) > 300:
                    continue
                with (meta_path.parent / 'events.jsonl').open(encoding='utf-8') as source:
                    for line in source:
                        try:
                            event = json.loads(line)
                            if isinstance(event, dict):
                                events.append(event)
                        except ValueError:
                            continue  # A concurrent partial row is not evidence.
            except (OSError, ValueError, KeyError, TypeError):
                continue
        result.update(sample_coverage(events, origin, length))
    except (OSError, ValueError, KeyError, wave.Error, ZeroDivisionError) as exc:
        result.update(coverage='unknown', coverage_error=str(exc))
    return result


def render_recording_summary(report):
    lines = ['# Итог записи', '']
    for label, title in [('remote', 'Системный звук'), ('microphone', 'Микрофон')]:
        t = report.get('tracks', {}).get(label, {})
        state = t.get('state', 'unknown')
        if label == 'microphone' and report.get('microphone') == 'disabled':
            lines.append('- Микрофон: отключён по настройке.')
            continue
        states = {'available':'сохранён', 'short':'неполная дорожка', 'empty':'нет аудиоданных',
                  'absent':'дорожка отсутствует', 'unreadable':'файл не читается', 'unknown':'не проверено'}
        text = states.get(state, state)
        if 'audio_seconds' in t:
            text += f"; {t['audio_seconds']:.1f} с"
        if t.get('missing_seconds', 0) > 0:
            text += f"; расхождение с ожидаемой длительностью {t['missing_seconds']:.1f} с"
        lines.append(f'- {title}: {text}.')
    j = report.get('journal', {})
    if j.get('coverage') == 'estimated':
        fraction = j.get('observed_fraction')
        coverage = f'{fraction:.0%}' if fraction is not None else 'не определено'
        lines.append(f'- Журнал имён: наблюдения покрывают {coverage} аудио; длинные пропуски не заполнены.')
        lines.append('- Покрытие журнала не подтверждает точность имён; тишина не считается ошибкой.')
    else:
        lines.append('- Журнал имён: покрытие не подтверждено.')
    if report.get('recording_error'):
        lines.append('- Ошибка записи: ' + str(report['recording_error']))
    lines.append('- Стенограмма и протокол: этим отчётом не подтверждаются; обработка выполняется отдельно.')
    return '\n'.join(lines) + '\n'


def save_recording_summary(session, report):
    text = render_recording_summary(report)
    target = Path(session) / 'recording-summary.md'
    temp = target.with_suffix('.tmp')
    temp.write_text(text, 'utf-8')
    temp.replace(target)
    return text
