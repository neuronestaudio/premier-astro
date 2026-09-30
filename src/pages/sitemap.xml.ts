// Builds /sitemap.xml from the pages that actually exist in this project, so a
// new page is listed the moment it is added. Priorities carry over from the
// previous site (src/data/sitemap-priorities.json); anything new gets a default.
import type { APIRoute } from 'astro';
import suburbs from '../data/suburbs.json';
import priorities from '../data/sitemap-priorities.json';

const SITE = 'https://premiermobiledetailing.com.au';
const EXCLUDE = new Set(['/thank-you', '/404', '/sitemap', '/sitemap.xml', '/quote']); // /sitemap is the human-readable index page

function defaultPriority(route: string): number {
  if (route === '/') return 1.0;
  if (route.startsWith('/services/')) return 0.8;
  if (route.startsWith('/mobile-detailing/')) return 0.6;
  return 0.7;
}

export const GET: APIRoute = () => {
  const files = Object.keys(import.meta.glob('./**/*.astro'));
  const routes = new Set<string>();
  for (const f of files) {
    let r = f.replace(/^\.\//, '/').replace(/\.astro$/, '').replace(/\/index$/, '');
    if (r === '') r = '/';
    if (r.includes('[')) continue; // dynamic routes are added from data below
    routes.add(r);
  }
  for (const s of suburbs as { slug: string }[]) routes.add(`/mobile-detailing/${s.slug}`);
  const list = [...routes].filter((r) => !EXCLUDE.has(r)).sort((a, b) => {
    const pa = (priorities as Record<string, number>)[a] ?? defaultPriority(a);
    const pb = (priorities as Record<string, number>)[b] ?? defaultPriority(b);
    return pb - pa || a.localeCompare(b);
  });
  const body =
    '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' +
    list.map((r) => {
      const p = ((priorities as Record<string, number>)[r] ?? defaultPriority(r)).toFixed(1);
      return `  <url><loc>${SITE}${r === '/' ? '/' : r}</loc><priority>${p}</priority></url>`;
    }).join('\n') +
    '\n</urlset>\n';
  return new Response(body, { headers: { 'Content-Type': 'application/xml; charset=utf-8' } });
};
