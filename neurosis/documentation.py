"""Markdown alternatives for bundled, trusted HTML documentation only."""
from html.parser import HTMLParser


class _Markdown(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag in ('p', 'pre', 'h2', 'h3', 'blockquote'):
            self.parts.append('\n\n')
        if tag == 'h2':
            self.parts.append('## ')
        elif tag == 'h3':
            self.parts.append('### ')
        elif tag == 'pre':
            self.parts.append('```text\n')
        elif tag == 'li':
            self.parts.append('\n- ')
        elif tag == 'blockquote':
            self.parts.append('> ')
        elif tag in ('strong', 'b'):
            self.parts.append('**')
        elif tag in ('em', 'i'):
            self.parts.append('*')
        elif tag == 'code':
            self.parts.append('`')
        elif tag == 'br':
            self.parts.append('\n')
        elif tag == 'a':
            self.links.append(dict(attrs).get('href', ''))
            self.parts.append('[')

    def handle_endtag(self, tag):
        if tag == 'a':
            self.parts.append('](' + self.links.pop() + ')')
        elif tag == 'pre':
            self.parts.append('\n```')
        elif tag in ('strong', 'b'):
            self.parts.append('**')
        elif tag in ('em', 'i'):
            self.parts.append('*')
        elif tag == 'code':
            self.parts.append('`')
        if tag in ('p', 'pre', 'h2', 'h3', 'blockquote', 'ul', 'ol', 'section', 'article'):
            self.parts.append('\n\n')

    def handle_data(self, data):
        self.parts.append(data)


def markdown_document(document: str) -> str:
    title, body = document.split('\n', 1)
    parser = _Markdown()
    parser.feed(body)
    return '# ' + title + '\n\n' + ''.join(parser.parts).strip() + '\n'
