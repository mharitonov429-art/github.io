/*
 * WebMCP для intellectclubonline.ru (статический сайт без форм).
 * Регистрирует два read-only инструмента для браузерных ИИ-агентов:
 *   1) search_articles — поиск статей по рубрикам и блогу;
 *   2) get_participation_links — ссылки для участия с пометкой «партнёрская» и «платно/бесплатно».
 * WebMCP — черновик стандарта: если браузер его не поддерживает,
 * скрипт молча ничего не делает и сайт работает как обычно.
 */
(function () {
  'use strict';

  var mc = (typeof document !== 'undefined' && document.modelContext) ||
           (typeof navigator !== 'undefined' && navigator.modelContext);
  if (!mc) return;

  var LISTS = ['/energiya/', '/mozg-i-myshlenie/', '/stress-i-emotsii/', '/samorazvitie/',
               '/otnosheniya/', '/liderstvo/', '/smysl-i-filosofiya/', '/son/', '/blogs/blog/'];
  var cache = null;

  function text(value) {
    return { content: [{ type: 'text', text: typeof value === 'string' ? value : JSON.stringify(value) }] };
  }

  function loadArticles() {
    if (cache) return cache;
    cache = Promise.all(LISTS.map(function (path) {
      return fetch(path, { credentials: 'omit' })
        .then(function (r) { return r.ok ? r.text() : ''; })
        .then(function (html) {
          if (!html) return [];
          var doc = new DOMParser().parseFromString(html, 'text/html');
          var out = [];
          doc.querySelectorAll('a[href^="/page/"], a[href^="/blogs/blog/"]').forEach(function (a) {
            var h = a.querySelector('h3, h4, h2');
            if (!h) return;
            var p = a.querySelector('p');
            out.push({
              title: h.textContent.trim(),
              summary: p ? p.textContent.trim() : '',
              url: new URL(a.getAttribute('href'), location.origin).href
            });
          });
          return out;
        })
        .catch(function () { return []; });
    })).then(function (lists) {
      var seen = {}, all = [];
      lists.forEach(function (list) {
        list.forEach(function (item) {
          if (!seen[item.url]) { seen[item.url] = true; all.push(item); }
        });
      });
      return all;
    });
    return cache;
  }

  var searchArticles = {
    name: 'search_articles',
    description: 'Поиск статей на сайте Интеллект-клуба Super Jump (intellectclubonline.ru) по ключевым словам: тема, название, рубрика. Возвращает до 10 страниц со ссылкой и кратким описанием.',
    inputSchema: {
      type: 'object',
      properties: {
        query: { type: 'string', description: 'Слова для поиска, например «стресс», «ксениалы», «улыбка», «интеллект-тренер»' }
      },
      required: ['query']
    },
    annotations: { readOnlyHint: true },
    execute: function (input) {
      var words = String((input && input.query) || '').toLowerCase().split(/\s+/).filter(Boolean);
      return loadArticles().then(function (all) {
        var found = all.filter(function (item) {
          var hay = (item.title + ' ' + item.summary + ' ' + item.url).toLowerCase();
          return words.every(function (w) { return hay.indexOf(w) !== -1; });
        }).slice(0, 10);
        return text(found.length ? found : 'Ничего не найдено. Полный список страниц: ' + new URL('/sitemap.xml', location.origin).href);
      }).catch(function () {
        return text('Не удалось загрузить список статей. Полный список страниц: ' + new URL('/sitemap.xml', location.origin).href);
      });
    }
  };

  var participationLinks = {
    name: 'get_participation_links',
    description: 'Ссылки для участия в проектах Super Jump с пометками: что бесплатно, что платно и что ссылки партнёрские (реферальные). Цены не указываются: они меняются, смотрите их на сайтах-источниках.',
    inputSchema: { type: 'object', properties: {} },
    annotations: { readOnlyHint: true },
    execute: function () {
      return text({
        super_jump_registration: {
          url: 'https://account.superjump.com/register/81982',
          description: 'Регистрация в личном кабинете Super Jump. В каталоге продуктов есть платные продукты (клубный статус, лицензия интеллект-тренера, медитации).',
          referral_link: true,
          paid_products_inside: true
        },
        super_jump_course: {
          url: 'https://account.superjump.com/landing/1u2rvfEVW8OE6yAvwLSUWQZe7GsHn41hmIjhnLppsrwj67sLYYYTSp0fETlL1uieeFlnbytrE52f4zOdVKralIZJ',
          description: 'Онлайн-курс по методике Super Jump: мини-группы 10–12 человек, 10 дней по одному часу. Условия и стоимость смотрите на странице курса.',
          referral_link: true
        },
        go_smile: {
          url: 'https://getgosmile.io/r/81982',
          description: 'GO SMILE — трекер улыбок',
          referral_link: true
        },
        smile_practice: {
          url: 'https://t.me/Ladaria7529',
          description: 'Бесплатная смехо-практика: мини-лекция 20 минут и пробное занятие; для получения ссылки напишите слово «СМЕХ» в Telegram.',
          free: true,
          referral_link: false
        },
        method_videos: {
          url: 'https://cp.puzzlebot.top/LbldJjCbn7WEBU',
          description: 'Короткие видео о методике Super Jump в Telegram-боте',
          referral_link: false
        }
      });
    }
  };

  [searchArticles, participationLinks].forEach(function (tool) {
    try {
      if (typeof mc.registerTool === 'function') {
        var r = mc.registerTool(tool);
        if (r && typeof r.catch === 'function') r.catch(function () {});
      }
    } catch (e) { /* инструмент уже зарегистрирован или политика браузера запрещает */ }
  });

  if (typeof mc.registerTool !== 'function' && typeof mc.provideContext === 'function') {
    try { mc.provideContext({ tools: [searchArticles, participationLinks] }); } catch (e) {}
  }
})();
