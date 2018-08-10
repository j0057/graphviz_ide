#!/usr/bin/env python3

import wsgiref.simple_server
import subprocess
import sys
import pprint
import textwrap
import re
import os
import functools

import xmlist

from urllib.parse import unquote_plus

def parse_get(func):
    @functools.wraps(func)
    def parse_get(environ, start_response, *a, **k):
        if environ['QUERY_STRING']:
            environ.update({'GET_' + key.upper(): unquote_plus(value)
                            for (key, value) in [pair.split('=', 1) for pair in environ['QUERY_STRING'].split('&')]})
        yield from func(environ, start_response, *a, **k)
    return parse_get

def render_index(environ, start_response):
    body = ['html',
        ['head',
            ['title', 'Graphviz IDE'],
            ['style', 'a:visited {color: blue}']],
        ['body',
            ['h1', 'Graphviz IDE'],
            ['p', 'Files in current directory with .dot extension:'],
            ['ul'] + [['li',
                ['span',
                    '(', ['a', ('href', '/svg/' + fn), 'svg'],
                    '/', ['a', ('href', '/png/' + fn), 'png'],
                    ')', fn]]
                for fn in os.listdir('.')
                if fn.endswith('.dot')],
            ['p', 'URL hacking functionality: add ?refresh=X to the URL to refresh the response every X seconds']]]
    start_response('200 OK', [
        ('Content-Type', 'text/html; charset=US-ASCII')
    ])
    yield b'<!DOCTYPE html>\n' + xmlist.serialize_ws(body).encode('ascii')

@parse_get
def render_dot(environ, start_response, output_format, dot_filename):
    etag = str(int(os.path.getmtime(dot_filename)))
    if etag == environ.get('HTTP_IF_NONE_MATCH'):
        start_response('304 Not Modified', [('Refresh', environ['GET_REFRESH'])] if 'GET_REFRESH' in environ else [])
        yield b''
    else:
        body = subprocess.check_output(['dot', dot_filename, '-T' + output_format])
        start_response('200 OK', [
            ('Content-Type', 'image/svg+xml; charset=US-ASCII' if output_format == 'svg' else 'image/png'),
            ('Cache-Control', 'no-cache, public, max-age=31536000, must-revalidate'),
            ('Etag', etag)
        ]
        + ([('Refresh', environ['GET_REFRESH'])] if 'GET_REFRESH' in environ else []))
        yield body

def render_404(environ, start_response):
    start_response('404 Not Found', [
        ('Content-Type', 'text/plain')
    ])
    yield b'404 Not Found'
    yield b'\n\n'
    yield environ['PATH_INFO']

def render_500(environ, start_response, ex):
        start_response('500 Internal Server Error', [
            ('Content-Type', 'text/plain'),
        ])
        yield b'500 Internal Server Error\n\n'
        yield type(ex).__name__.encode('ascii')
        yield b': '
        yield str(ex).encode('ascii')

def route_handler(environ, start_response, *routes):
    for (regex, handler) in routes:
        match = re.match(regex, environ['PATH_INFO'])
        if match:
            yield from handler(environ, start_response, *match.groups())
            break
    else:
        yield from render_404(environ, start_response)

def app(environ, start_response):
    try:
        yield from route_handler(environ, start_response,
            (r'^/$',            render_index),
            (r'^/(svg)/(.*)$',  render_dot),
            (r'^/(png)/(.*)$',  render_dot))
    except Exception as e:
        yield from render_500(environ, start_response, e)

if __name__ == '__main__':
    port = int(sys.argv[1]) if sys.argv[1:] else 8000
    print('Graphviz IDE serving HTTP on port', port)
    httpd = wsgiref.simple_server.make_server('', port, app)
    httpd.serve_forever()
