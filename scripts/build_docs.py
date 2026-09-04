#!/usr/bin/env python3
"""Tiny build-time renderer for trusted project Markdown only, never engrams."""
import html
import re
from pathlib import Path

root = Path(__file__).resolve().parent.parent / 'public'
for path in root.glob('*.md'):
    lines = path.read_text().splitlines()
    output, paragraph, code = [], [], None
    def flush():
        if paragraph:
            text = html.escape(' '.join(paragraph))
            text = re.sub(r'\[([^\]]+)\]\(((?:/|https://)[^ )]*)\)', r'<a href="\2">\1</a>', text)
            output.append('<p>'+text+'</p>')
            paragraph.clear()
    for line in lines[1:]:
        if line.startswith('```'):
            flush()
            if code is None:
                code = []
            else:
                output.append('<pre>'+html.escape('\n'.join(code))+'</pre>')
                code = None
        elif code is not None:
            code.append(line)
        elif line.startswith('## '):
            flush()
            heading = line[3:]
            anchor = re.sub('[^a-z0-9]+','-',heading.lower()).strip('-')
            output.append(f'<h2 id="{anchor}">'+html.escape(heading)+'</h2>')
        elif line:
            paragraph.append(line)
        else:
            flush()
    flush()
    path.with_suffix('.html').write_text(lines[0][2:]+'\n'+'\n'.join(output)+'\n')
