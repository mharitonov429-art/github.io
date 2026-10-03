# intellectclubonline.ru

Статический сайт Интеллект-клуба Super Jump. Публикуется на GitHub Pages через GitHub Actions.

## Как добавить статью
1. Скопируйте `_templates/article.html` (или возьмите готовый код страницы из чата с промтом).
2. Сохраните как `page/<slug>/index.html` (пост блога — `blogs/blog/<slug>/index.html`).
   `slug` для статей со старого сайта должен совпадать со старым адресом.
3. Обязательно заполните: `title`, `description`, `canonical`, `article:section` (ключ рубрики), `article:published_time`.
4. Commit → через 1–2 минуты страница на сайте, а также в списке рубрики, на главной и в `sitemap.xml`.

## Ключи рубрик (`article:section`)
energiya · mozg-i-myshlenie · stress-i-emotsii · samorazvitie · otnosheniya · liderstvo · smysl-i-filosofiya · son · blog

## Что делает сборка (`tools/build.py`)
- подставляет списки статей между `<!--LIST:... -->` и `<!--/LIST-->`;
- строит `sitemap.xml` (страницы с `noindex` не попадают);
- проверяет canonical, title, description, один счётчик Метрики, один H1 — предупреждения видны в логе Actions.

## Страницы-заглушки с noindex
`o-nas`, `kontakty`, `politika`, `oferta`, `super-jump/kak-prohodit-kurs`, `super-jump/intellekt-trener` — заполните и удалите строку `<meta name="robots" content="noindex, follow">`.
