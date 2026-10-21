"""Save observed homework as Markdown using only the standard library."""
import argparse
import datetime as dt
import json
from pathlib import Path
import shutil
from urllib.parse import urlsplit


def cell(value):
    return str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '&#124;').replace('\r', '').replace('\n', '<br>')


def save(data, folder):
    start = dt.date.fromisoformat(data['week_start'])
    if start.weekday() != 0:
        raise ValueError('week_start must be Monday')
    days = {start + dt.timedelta(days=i) for i in range(7)}
    checked = {dt.date.fromisoformat(v) for v in data['checked_days']}
    if not checked.issubset(days):
        raise ValueError('Checked day outside requested week')
    complete = data['complete']
    if not isinstance(complete, bool) or (complete and checked != days):
        raise ValueError('A complete report requires all seven days to be checked')
    child = data['child'].strip()
    if not child:
        raise ValueError('Child profile is required')
    rows = []
    for task in data['tasks']:
        due = dt.date.fromisoformat(task['due'])
        if due not in days or due not in checked:
            raise ValueError('Task date must be in a checked day of the week')
        if not task['subject'].strip() or not task['text'].strip():
            raise ValueError('Subject and assignment text are required')
        materials = []
        for item in task.get('materials', []):
            title, url = item['title'], item.get('url', '')
            if url:
                parsed = urlsplit(url)
                if parsed.scheme not in ('https', 'http') or not parsed.netloc:
                    raise ValueError('Material links must be HTTP(S) URLs')
                url = url.replace(' ', '%20').replace('<', '%3C').replace('>', '%3E').replace('|', '%7C').replace('\n', '').replace('\r', '')
                label = cell(title).replace('[', '&#91;').replace(']', '&#93;')
                materials.append('[' + label + '](<' + url + '>)')
            else:
                materials.append(cell(title))
        rows.append((due, task['subject'], '| ' + ' | '.join([cell(due.isoformat()), cell(task['subject']), cell(task['text']), cell(task.get('status', 'Не указан')), '<br>'.join(materials) or '—']) + ' |'))
    end = start + dt.timedelta(days=6)
    marker = '<!-- mesh-homework:complete=' + str(complete).lower() + ' -->'
    lines = ['# Домашние задания', '', marker, '', '**Ребёнок:** ' + cell(child), '**Период сдачи:** ' + str(start) + ' — ' + str(end), '**Собрано:** ' + dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'), '**Источник:** https://school.mos.ru/diary/homeworks/homeworks', '**Проверено дней:** ' + str(len(checked)) + '/7', '**Заданий:** ' + str(len(rows)), '']
    if not complete:
        lines += ['> НЕПОЛНЫЙ ОТЧЁТ. Не проверены даты: ' + ', '.join(map(str, sorted(days - checked))), '']
    lines += ['| Дата сдачи | Предмет | Задание | Статус | Материалы |', '|---|---|---|---|---|']
    lines += [row[2] for row in sorted(rows, key=lambda r: (r[0], r[1]))]
    if not rows:
        lines += ['', 'На проверенных датах задания не обнаружены.' if checked else 'Задания не проверены.']
    folder = Path(folder).resolve()
    folder.mkdir(parents=True, exist_ok=True)
    name = 'Homework_' + str(start) + '_' + str(end)
    target = folder / (name + '.md')
    if target.exists() and '**Ребёнок:** ' + cell(child) + '\n' not in target.read_text('utf-8'):
        raise ValueError('This folder already contains a report for another child; select a separate folder')
    if target.exists() and not complete and '<!-- mesh-homework:complete=true -->' in target.read_text('utf-8'):
        target = folder / (name + '_partial.md')
    if target.exists():
        stamp = dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        shutil.copy2(target, target.with_name(target.name + '.' + stamp + '.bak'))
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=folder, prefix='homework-', suffix='.tmp', delete=False) as stream:
        stream.write('\n'.join(lines) + '\n')
        temporary = Path(stream.name)
    try:
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return target


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    print(save(json.loads(args.input.read_text('utf-8-sig')), args.output_dir))
