#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Сборка сайта: копирует файлы в dist/, подставляет списки статей, строит sitemap.xml.
Запускается автоматически в GitHub Actions при каждом push. Локально: python3 tools/build.py
"""
import os, re, shutil, html, sys
from datetime import datetime

SRC = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(SRC, 'dist')
SITE = 'https://intellectclubonline.ru'
SKIP_TOP = {'.git', '.github', 'tools', '_templates', 'dist', 'README.md', '.gitignore'}

RUBRICS = {
    'energiya': 'Энергия', 'mozg-i-myshlenie': 'Мозг и мышление',
    'stress-i-emotsii': 'Стресс и эмоциональное состояние', 'samorazvitie': 'Саморазвитие',
    'otnosheniya': 'Отношения', 'liderstvo': 'Лидерство',
    'smysl-i-filosofiya': 'Смысл и философия', 'son': 'Сон', 'blog': 'Блог',
}
warnings = []

def meta(text, pattern):
    m = re.search(pattern, text, re.S | re.I)
    return html.unescape(m.group(1).strip()) if m else ''

def parse(path, rel):
    t = open(path, encoding='utf-8').read()
    d = {
        'rel': rel, 'text': t,
        'title': meta(t, r'<title>(.*?)</title>'),
        'h1': re.sub(r'<[^>]+>', '', meta(t, r'<h1[^>]*>(.*?)</h1>')).strip(),
        'desc': meta(t, r'<meta\s+name="description"\s+content="(.*?)"'),
        'canonical': meta(t, r'<link\s+rel="canonical"\s+href="(.*?)"'),
        'published': meta(t, r'property="article:published_time"\s+content="(.*?)"'),
        'modified': meta(t, r'property="article:modified_time"\s+content="(.*?)"'),
        'section': meta(t, r'property="article:section"\s+content="(.*?)"'),
        'noindex': bool(re.search(r'<meta\s+name="robots"\s+content="[^"]*noindex', t, re.I)),
    }
    d['url_path'] = '/' + rel.replace('index.html', '').replace('\\', '/')
    return d

def card(a):
    date = ''
    if re.match(r'\d{4}-\d{2}-\d{2}', a['published']):
        y, m, dd = a['published'][:10].split('-'); date = f'{dd}.{m}.{y}'
    rub = RUBRICS.get(a['section'], '')
    return f'''<a href="{a['url_path']}" class="block bg-white p-7 rounded-3xl border border-slate-200 shadow-sm hover:shadow-xl transition-all group">
    <div class="flex items-center justify-between mb-4 text-xs font-black uppercase text-slate-400"><span>{html.escape(rub)}</span><span>{date}</span></div>
    <h3 class="text-xl font-black mb-3 group-hover:text-blue-600 transition-colors">{html.escape(a['h1'] or a['title'])}</h3>
    <p class="text-slate-600 text-sm line-clamp-3">{html.escape(a['desc'])}</p>
    <span class="inline-block mt-4 text-blue-600 font-black uppercase text-xs tracking-widest">Читать →</span>
</a>'''

def main():
    if os.path.exists(DIST): shutil.rmtree(DIST)
    os.makedirs(DIST)
    for name in os.listdir(SRC):
        if name in SKIP_TOP: continue
        s, d = os.path.join(SRC, name), os.path.join(DIST, name)
        if os.path.isdir(s): shutil.copytree(s, d)
        else: shutil.copy2(s, d)

    pages = []
    for root, _, files in os.walk(DIST):
        for f in files:
            if f.endswith('.html'):
                p = os.path.join(root, f)
                pages.append(parse(p, os.path.relpath(p, DIST)))

    # статьи = страницы с article:section, не noindex
    articles = [p for p in pages if p['section'] and not p['noindex']]
    articles.sort(key=lambda a: a['published'] or '0000', reverse=True)

    # проверки
    seen_t, seen_c = {}, {}
    for p in pages:
        if p['rel'] == '404.html': continue
        expected = SITE + p['url_path']
        if p['canonical'] != expected:
            warnings.append(f"canonical не совпадает с адресом страницы: {p['rel']}: {p['canonical']} (ожидалось {expected})")
        if p['text'].count('mc.yandex.ru/metrika/tag.js') != 1:
            warnings.append(f"счётчик Метрики должен быть ровно один: {p['rel']}")
        if '[' in p['title'] and ']' in p['title']:
            warnings.append(f"в title остались [поля шаблона]: {p['rel']}")
        if not p['noindex']:
            if p['title'] in seen_t: warnings.append(f"одинаковый title: {p['rel']} и {seen_t[p['title']]}")
            seen_t[p['title']] = p['rel']
            if p['desc'] and p['desc'] in seen_c: warnings.append(f"одинаковый description: {p['rel']} и {seen_c[p['desc']]}")
            seen_c[p['desc']] = p['rel']
            if not (50 <= len(p['desc']) <= 200): warnings.append(f"длина description {len(p['desc'])}: {p['rel']}")
            if len(p['title']) > 75: warnings.append(f"title длиннее 75 символов: {p['rel']}")
        if p['section'] and p['section'] not in RUBRICS:
            warnings.append(f"неизвестный article:section «{p['section']}»: {p['rel']}")
        if p['section'] and not p['published']:
            warnings.append(f"нет article:published_time: {p['rel']}")
        if p['text'].count('<h1') != 1:
            warnings.append(f"H1 должен быть один (найдено {p['text'].count('<h1')}): {p['rel']}")

    # списки <!--LIST:key limit=N--> ... <!--/LIST-->
    rx = re.compile(r'<!--LIST:(\w[\w-]*)(?:\s+limit=(\d+))?-->.*?<!--/LIST-->', re.S)
    for p in pages:
        if '<!--LIST:' not in p['text']: continue
        def repl(m):
            key, lim = m.group(1), m.group(2)
            items = articles if key == 'all' else [a for a in articles if a['section'] == key]
            if lim: items = items[:int(lim)]
            if not items:
                body = '<p class="text-slate-500 md:col-span-2 lg:col-span-3">Материалы скоро появятся.</p>'
            else:
                body = '\n'.join(card(a) for a in items)
            return f'<!--LIST:{key}{(" limit="+lim) if lim else ""}-->\n{body}\n<!--/LIST-->'
        new = rx.sub(repl, p['text'])
        open(os.path.join(DIST, p['rel']), 'w', encoding='utf-8').write(new)

    # превью на github.io/<репозиторий>/: добавляем префикс к внутренним ссылкам
    base = os.environ.get('BASE_PATH', '').strip().rstrip('/')
    if base:
        rx_link = re.compile(r'(\b(?:href|src)=")/(?!/)')
        for p in pages:
            fp = os.path.join(DIST, p['rel'])
            t = open(fp, encoding='utf-8').read()
            open(fp, 'w', encoding='utf-8').write(rx_link.sub(lambda m: m.group(1) + base + '/', t))
        print(f'Превью-режим: внутренние ссылки получили префикс {base}')

    # sitemap.xml
    urls = [p for p in pages if not p['noindex'] and p['rel'] != '404.html']
    urls.sort(key=lambda p: (p['url_path'] != '/', p['url_path']))
    out = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for p in urls:
        out.append('<url>')
        out.append(f"<loc>{SITE}{p['url_path']}</loc>")
        lm = (p['modified'] or p['published'])[:10]
        if re.match(r'\d{4}-\d{2}-\d{2}$', lm): out.append(f'<lastmod>{lm}</lastmod>')
        out.append('</url>')
    out.append('</urlset>')
    open(os.path.join(DIST, 'sitemap.xml'), 'w', encoding='utf-8').write('\n'.join(out) + '\n')

    print(f'Страниц: {len(pages)}, в sitemap: {len(urls)}, статей в списках: {len(articles)}')
    for w in warnings: print('ВНИМАНИЕ:', w)
    if os.environ.get('STRICT') and warnings: sys.exit(1)

if __name__ == '__main__':
    main()
