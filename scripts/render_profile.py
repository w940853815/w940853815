"""Render the profile artwork from the same activity block updated by Douban."""

import base64
from html import escape
from pathlib import Path
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
START = '<!-- DOUBAN-ACTIVITIES:START -->'
END = '<!-- DOUBAN-ACTIVITIES:END -->'
INK = '#eef3f7'
MUTED = '#a5b2c2'
MINT = '#9de2c4'
LINE = '#2b3745'


def activities_from(markdown):
    if markdown.count(START) != 1 or markdown.count(END) != 1:
        raise ValueError('Expected one pair of Douban activity markers')
    if markdown.index(START) > markdown.index(END):
        raise ValueError('Douban activity markers are out of order')
    entries = []
    for line in markdown.split(START)[1].split(END)[0].splitlines():
        if not line.strip():
            continue
        match = re.fullmatch(r'- \[([^\n]+)\]\((https://[^\s]+)\)', line)
        if not match:
            raise ValueError(f'Unrecognized activity: {line}')
        label, url = match.groups()
        status, sep, title = label.partition(' ')
        if not sep or not title.strip():
            raise ValueError('Activity must contain a status and a title')
        title = ''.join(c for c in title if unicodedata.category(c) != 'Cf')
        entries.append((status, title, url))
    return entries[:3]


def units(value):
    return sum(0 if unicodedata.combining(c) else
               2 if unicodedata.east_asian_width(c) in ('W', 'F') else 1
               for c in value)


def wrap_title(value, limit):
    """Keep long titles inside two lines; the full title stays in the README."""
    lines, current = [], ''
    for char in value:
        if current and units(current + char) > limit:
            lines.append(current.rstrip())
            current = ''
        current += char
    if current:
        lines.append(current.strip())
    if len(lines) > 2:
        last = lines[1]
        while units(last + '…') > limit:
            last = last[:-1]
        lines = [lines[0], last.rstrip() + '…']
    return lines


def text(x, y, value, size=18, color=INK, weight=400, anchor='start'):
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{color}" '
            f'font-weight="{weight}" text-anchor="{anchor}">{escape(value)}</text>')


def command(x, y, value, size=17):
    return text(x, y, '$', size, MINT) + text(x + size * 1.25, y, value, size)


def folder(x, y):
    return (f'<path d="M{x} {y}h8l4 4h12v16H{x}Z" '
            f'fill="none" stroke="{MINT}" stroke-width="1.5" stroke-linejoin="round"/>')


def render(entries, mobile, fonts):
    width, inset = (420, 28) if mobile else (880, 42)
    row_top, row_height = (536, 104) if mobile else (428, 76)
    row_end = row_top + max(1, len(entries)) * row_height
    footer = row_end + 26
    height = footer + 60
    description = 'wrd · FIT2CLOUD · Beijing。' + '；'.join(s + ' ' + t for s, t, _ in entries)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">',
             '<title id="title">wrd — a developer’s workspace</title>',
             f'<desc id="desc">{escape(description)}</desc>',
             '<style>' + ''.join(
                 f'@font-face{{font-family:JB;src:url(data:font/woff2;base64,{data}) format("woff2");font-weight:{weight}}}'
                 for weight, data in fonts.items()) +
             'text{font-family:JB,"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",sans-serif}'
             '</style>',
             f'<rect x=".5" y=".5" width="{width-1}" height="{height-1}" rx="16" fill="#121820" stroke="{LINE}"/>',
             f'<path d="M16 .5H{width-16}Q{width-.5} .5 {width-.5} 16V48H.5V16Q.5 .5 16 .5Z" fill="#1a222d"/>',
             f'<path d="M1 48H{width-1}" stroke="{LINE}"/>']
    for x, color in [(25, '#718096'), (39, '#718096'), (53, MINT)]:
        parts.append(f'<circle cx="{x}" cy="24" r="3.5" fill="{color}"/>')
    parts += [text(76, 29, 'wrd@github: ~', 13, MUTED),
              text(width-24, 29, 'README.md', 12, MUTED, anchor='end')]

    parts += [command(inset, 90 if mobile else 100, 'whoami', 18 if mobile else 17),
              text(inset-2, 168 if mobile else 183, 'wrd', 66, INK, 700),
              text(inset, 208 if mobile else 225, '@w940853815', 20, MUTED),
              text(inset, 250 if mobile else 266, 'FIT2CLOUD · Beijing', 17, INK),
              text(inset, 289 if mobile else 306, '参与 JumpServer 生态的开发与维护。', 20 if mobile else 18),
              text(inset, 320 if mobile else 335, '工作之外，读书、看电影。', 20 if mobile else 18)]
    if mobile:
        parts.append(command(inset, 367, 'ls projects/', 18))
        for x, title in [(28, 'JumpServer'), (199, 'Lina'), (300, 'Luna')]:
            parts += [folder(x, 394), text(x+32, 411, title, 17, MINT)]
        boundary = 440
    else:
        parts += [f'<path d="M546 76V334" stroke="{LINE}"/>',
                  command(581, 100, 'ls projects/'),
                  f'<path d="M588 139V295M588 167H604M588 227H604M588 287H604" fill="none" stroke="#526172"/>']
        for y, title in [(153, 'JumpServer'), (213, 'Lina'), (273, 'Luna')]:
            parts += [folder(619, y), text(659, y+19, title, 22, MINT)]
        boundary = 364
    parts.append(f'<path d="M1 {boundary}H{width-1}" stroke="{LINE}"/>')
    parts.append(command(inset, 484 if mobile else 405, 'tail -3 life.log', 18 if mobile else 17))
    parts.append(text(inset if mobile else width-inset, 515 if mobile else 405,
                      '最近在读 · 在看', 15, MUTED, anchor='start' if mobile else 'end'))

    for i, (status, title, _) in enumerate(entries):
        top = row_top + i * row_height
        if status in ('在读', '在看'):
            parts.append(f'<rect x="16" y="{top+3}" width="{width-32}" height="{row_height-6}" rx="8" fill="#1a2c29"/>')
        color = MINT if status in ('在读', '在看') else MUTED
        parts.append(text(inset, top+23 if mobile else top+44, status, 16 if mobile else 15, color))
        tx, ty = (inset, top+57) if mobile else (124, top+44)
        limit = int((width-inset-tx) / (22 * .6))
        bilingual = re.fullmatch(r'(.+?[\u3400-\u9fff])\s+([A-Za-z].+)', title)
        if bilingual and units(bilingual[1]) <= limit:
            parts += [text(tx, ty-5 if not mobile else ty, bilingual[1], 22),
                      text(tx, ty+19 if not mobile else ty+27, wrap_title(bilingual[2], limit+10)[0], 14 if not mobile else 16, MUTED)]
        else:
            lines = wrap_title(title, limit)
            y = ty - (13 if len(lines) > 1 and not mobile else 0)
            for n, line in enumerate(lines):
                parts.append(text(tx, y+n*27, line, 22))
        if i < len(entries)-1:
            parts.append(f'<path d="M{inset} {top+row_height}H{width-inset}" stroke="#24313e"/>')
    if not entries:
        parts.append(text(inset, row_top+48, '暂无近期书影音记录', 20, MUTED))

    parts += [f'<path d="M1 {footer}H{width-1}" stroke="{LINE}"/>',
              text(inset, footer+37, 'wrd@github:~ $', 14, MINT),
              f'<rect x="{inset+134}" y="{footer+24}" width="7" height="16" rx="1" fill="{MINT}"/>',
              text(width-inset, footer+37, f'{len(entries)} entries', 12, MUTED, anchor='end'),
              '</svg>']
    return '\n'.join(parts) + '\n'


def main():
    entries = activities_from((ROOT/'README.md').read_text(encoding='utf-8'))
    fonts = {weight: base64.b64encode((ROOT/'assets/fonts'/name).read_bytes()).decode('ascii')
             for weight, name in [(400, 'JetBrainsMono-Regular.woff2'), (700, 'JetBrainsMono-Bold.woff2')]}
    # Build both variants before replacing either file, so bad input keeps the last artwork.
    output = {name: render(entries, mobile, fonts) for name, mobile in
              [('profile.svg', False), ('profile-mobile.svg', True)]}
    for name, svg in output.items():
        (ROOT/'assets'/name).write_text(svg, encoding='utf-8')


if __name__ == '__main__':
    main()
