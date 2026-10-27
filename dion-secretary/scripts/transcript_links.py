"""Obsidian block anchors and timestamp references without changing spoken text."""
from bisect import bisect_right
from collections import Counter
import re

TIME = r'\d{2}:\d{2}(?::\d{2})?'
TURN = re.compile(rf'^\[({TIME})\] .+')
ANCHOR = re.compile(r' \^(t-\d{2}-\d{2}-\d{2}(?:-\d+)?)$')
REFERENCE = re.compile(rf'```[\s\S]*?```|~~~[\s\S]*?~~~|\[\[[^\n]*?\]\]|\[[^\n\]]+\]\([^\n)]*\)|`[^`\n]*`|(?P<stamp>\[(?P<start>{TIME})(?:\s*[–—-]\s*{TIME})?\])')


def seconds(stamp):
    parts = list(map(int, stamp.split(':')))
    if any(value >= 60 for value in parts[-2:]):
        raise ValueError('Invalid timestamp')
    return sum(value * 60**index for index, value in enumerate(reversed(parts)))


def anchor_transcript(text):
    counts = Counter()
    lines = []
    for line in text.splitlines():
        match = TURN.match(line)
        if match:
            value = seconds(match[1])
            key = f't-{value//3600:02d}-{value//60%60:02d}-{value%60:02d}'
            counts[key] += 1
            suffix = '' if counts[key] == 1 else '-' + str(counts[key])
            line = ANCHOR.sub('', line) + ' ^' + key + suffix
            if lines and lines[-1]:
                lines.append('')
        lines.append(line)
    return '\n'.join(lines).rstrip() + '\n'


def link_timestamps(body, transcript_text, transcript_name):
    points = {}
    for line in transcript_text.splitlines():
        turn, anchor = TURN.match(line), ANCHOR.search(line)
        if turn and anchor:
            points.setdefault(seconds(turn[1]), anchor[1])
    if not points:
        return body
    ordered = sorted(points)
    # Escape characters that have syntax inside Obsidian wikilinks / Markdown tables.
    target = transcript_name.replace('|', '&#124;').replace('[', '&#91;').replace(']', '&#93;')
    def replace(match):
        if match['stamp'] is None:
            return match[0]
        position = max(0, bisect_right(ordered, seconds(match['start'])) - 1)
        anchor = points[ordered[position]]
        line_start = body.rfind('\n', 0, match.start()) + 1
        delimiter = r'\|' if body[line_start:match.start()].lstrip().startswith('|') else '|'
        return f'[[{target}#^{anchor}{delimiter}{match["stamp"][1:-1]}]]'
    return REFERENCE.sub(replace, body)
