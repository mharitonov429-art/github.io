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
errors = []

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
        'ogtitle': meta(t, r'property="og:title"\s+content="(.*?)"'),
        'redirect': 'http-equiv="refresh"' in t,
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
    <h3 class="text-xl font-black mb-3 group-hover:text-blue-600 transition-colors">{html.escape(a['ogtitle'] or a['h1'] or a['title'])}</h3>
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

    # проверки: ERR останавливает публикацию, WARN только показывается
    seen_t, seen_c = {}, {}
    valid = {p['url_path'] for p in pages}
    PH = re.compile(r'\[(?:[А-ЯЁA-Z][А-ЯЁA-Z0-9 .,\-/]+|ТЕМА[^\]]*|120–160[^\]]*|N)\]')
    for p in pages:
        if p['rel'] == '404.html' or p['redirect']: continue
        r = p['rel']; t = p['text']
        expected = SITE + p['url_path']
        if p['canonical'] != expected:
            errors.append(f"canonical не совпадает с адресом страницы: {r}: {p['canonical']} (ожидалось {expected})")
        ph = PH.findall(re.sub(r'<script(?![^>]*ld\+json).*?</script>', '', t, flags=re.S))
        if ph:
            errors.append(f"остались поля шаблона {sorted(set(ph))[:4]}: {r}")
        if t.count('mc.yandex.ru/metrika/tag.js') != 1:
            warnings.append(f"счётчик Метрики должен быть ровно один: {r}")
        if t.count('<h1') != 1:
            warnings.append(f"H1 должен быть один (найдено {t.count('<h1')}): {r}")
        if not p['noindex']:
            if p['title'] in seen_t: warnings.append(f"одинаковый title: {r} и {seen_t[p['title']]}")
            seen_t[p['title']] = p['rel']
            if p['desc'] and p['desc'] in seen_c: warnings.append(f"одинаковый description: {r} и {seen_c[p['desc']]}")
            seen_c[p['desc']] = p['rel']
        # внутренние ссылки
        body_links = re.findall(r'href="(/[^"#?]*)"', re.sub(r'<script.*?</script>', '', t, flags=re.S))
        for h in sorted(set(body_links)):
            if h.endswith('/'):
                if h not in valid: warnings.append(f"ссылка на несуществующую страницу {h}: {r}")
            elif not os.path.exists(os.path.join(DIST, h.lstrip('/'))):
                warnings.append(f"ссылка на несуществующий файл {h}: {r}")
        # проверки статей
        if not p['section']: continue
        if p['section'] not in RUBRICS:
            errors.append(f"неизвестный article:section «{p['section']}»: {r}")
        if not re.match(r'\d{4}-\d{2}-\d{2}$', p['published']):
            errors.append(f"нет или неверный article:published_time: {r}")
        if len(p['title']) > 60: warnings.append(f"title длиннее 60 символов ({len(p['title'])}): {r}")
        if not (120 <= len(p['desc']) <= 160): warnings.append(f"description {len(p['desc'])} симв. (нужно 120–160): {r}")
        m = re.search(r'<article>(.*?)</article>', t, re.S)
        body = m.group(1) if m else ''
        body = re.sub(r'<aside.*?</aside>', '', body, flags=re.S)
        body = re.sub(r'<div class="mt-16 bg-blue-600.*', '', body, flags=re.S)
        words = len(re.sub(r'<[^>]+>', ' ', body).split())
        if words < 1000: warnings.append(f"короткий текст: {words} слов (норма 1 200–2 000): {r}")
        elif words > 2300: warnings.append(f"слишком длинный текст: {words} слов: {r}")
        h2 = len(re.findall(r'<h2', body))
        if not (4 <= h2 <= 6): warnings.append(f"H2 должно быть 4–6, найдено {h2}: {r}")
        lists = len(re.findall(r'<(?:ul|ol)\b', body))
        if lists > 2: warnings.append(f"списков в тексте {lists} (максимум 2): {r}")
        if body.count('<blockquote') != 1 and 'цитат' not in p['h1'].lower(): warnings.append(f"цитат должно быть ровно одна, найдено {body.count('<blockquote')}: {r}")
        if 'gosmile_click' not in t: warnings.append(f"устаревший шаблон: нет скрипта целей Метрики (gosmile_click): {r}")
        if 'onclick' in t: warnings.append(f"найден onclick (цели считает общий скрипт): {r}")
        if re.search(r'<!--(?!\s*/?LIST)', body): warnings.append(f"в тексте остались HTML-комментарии/TODO: {r}")
        if not re.search(r'href="/[^"]+"', body): warnings.append(f"в тексте нет внутренних ссылок: {r}")

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
        rx_link = re.compile(r'(\b(?:href|src)="|http-equiv="refresh" content="0; url=|location\.replace\(\')/(?!/)')
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
    ci = bool(os.environ.get('GITHUB_ACTIONS'))
    for e in errors: print(('::error::' if ci else 'ОШИБКА: ') + e)
    for w in warnings: print(('::warning::' if ci else 'ВНИМАНИЕ: ') + w)
    summ = os.environ.get('GITHUB_STEP_SUMMARY')
    if summ:
        with open(summ, 'a', encoding='utf-8') as f:
            f.write(f'## Проверка сайта\nСтраниц: {len(pages)} · в sitemap: {len(urls)} · статей: {len(articles)}\n\n')
            if errors: f.write('### Ошибки (публикация остановлена)\n' + '\n'.join(f'- {e}' for e in errors) + '\n\n')
            if warnings: f.write('### Предупреждения\n' + '\n'.join(f'- {w}' for w in warnings) + '\n')
            if not errors and not warnings: f.write('Замечаний нет.\n')
    if errors:
        print('Публикация остановлена: исправьте ошибки выше.'); sys.exit(1)
    if os.environ.get('STRICT') and warnings: sys.exit(1)

if __name__ == '__main__':
    main()
