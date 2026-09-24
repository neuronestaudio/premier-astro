// @ts-check
import { defineConfig } from 'astro/config';

// Static site. Every route builds to <route>/index.html so Vercel serves clean
// URLs exactly as the previous static mirror did (cleanUrls + trailingSlash:false
// live in vercel.json).
export default defineConfig({
  site: 'https://premiermobiledetailing.com.au',
  output: 'static',
  trailingSlash: 'never',
  build: { format: 'directory' },
  // The page bodies were baked from a rendered DOM; keep their whitespace as-is.
  compressHTML: false,
});
