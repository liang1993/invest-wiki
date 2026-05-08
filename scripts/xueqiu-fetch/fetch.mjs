// fetch.mjs — Playwright + stealth 抓雪球文章
//
// 用法：
//   node fetch.mjs login                          # 首次手动登录（弹窗扫码/输密码）
//   node fetch.mjs fetch <url-or-id>              # 抓单篇
//   node fetch.mjs fetch-collection <url>         # 抓文集页（解析出所有文章链接）+ 全部正文
//
// 文件输出到 ../../raw/articles/stocks/姜诚/<status_id>.md（hardcoded 给本次任务）

import { chromium } from 'playwright-extra';
import stealth from 'puppeteer-extra-plugin-stealth';
import TurndownService from 'turndown';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

chromium.use(stealth());

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PROFILE_DIR = path.join(__dirname, '.xq-profile');
const OUT_DIR = path.resolve(__dirname, '../../raw/articles/stocks/姜诚');
fs.mkdirSync(OUT_DIR, { recursive: true });

const td = new TurndownService({ headingStyle: 'atx', codeBlockStyle: 'fenced' });
td.addRule('keep-iframe', { filter: ['iframe', 'script', 'style'], replacement: () => '' });

async function launch(headless = false) {
  return await chromium.launchPersistentContext(PROFILE_DIR, {
    headless,
    viewport: { width: 1280, height: 900 },
    userAgent:
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
    args: ['--disable-blink-features=AutomationControlled'],
    locale: 'zh-CN',
  });
}

function waitEnter(prompt) {
  return new Promise((resolve) => {
    process.stdout.write(prompt);
    process.stdin.resume();
    process.stdin.once('data', () => {
      process.stdin.pause();
      resolve();
    });
  });
}

async function loginFlow() {
  const ctx = await launch(false);
  const page = ctx.pages()[0] ?? (await ctx.newPage());
  await page.goto('https://xueqiu.com/', { waitUntil: 'domcontentloaded' });
  console.log('在弹出的 Chromium 窗口里完成登录（扫码或账号密码），登录成功后回到此终端按 Enter');
  await waitEnter('登录完成后按 Enter 继续 > ');
  // verify login
  const cookies = await ctx.cookies('https://xueqiu.com');
  const tok = cookies.find((c) => c.name === 'xq_a_token');
  if (!tok) {
    console.error('警告：未检测到 xq_a_token cookie，登录可能未完成。如继续抓取请重试。');
  } else {
    console.log('已检测到 xq_a_token，登录态已落到', PROFILE_DIR);
  }
  await ctx.close();
}

function parseStatusId(input) {
  const m = String(input).match(/(\d{6,})/);
  if (!m) throw new Error(`无法解析 status_id: ${input}`);
  return m[1];
}

function statusUrl(arg) {
  if (/^https?:/.test(arg)) return arg;
  // assume "<uid>/<sid>" or just "<sid>" (default uid 2245748859 for 姜诚)
  if (arg.includes('/')) return `https://xueqiu.com/${arg}`;
  return `https://xueqiu.com/2245748859/${arg}`;
}

async function fetchOne(page, url) {
  console.log(`→ ${url}`);
  await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 30000 });
  // 等到正文出来
  await page
    .waitForSelector('article.article__bd, .status__main__article, .article__bd__detail', {
      timeout: 15000,
    })
    .catch(() => null);
  // 给 WAF / lazy content 一点时间
  await page.waitForTimeout(1500);

  const data = await page.evaluate(() => {
    const titleEl =
      document.querySelector('h1.article__bd__title') ||
      document.querySelector('.article__bd__title') ||
      document.querySelector('h1');
    const title = titleEl ? titleEl.innerText.trim() : document.title;
    const dateEl =
      document.querySelector('.article__bd__from time') ||
      document.querySelector('.article__bd__from') ||
      document.querySelector('time');
    const date = dateEl ? dateEl.innerText.trim() : '';
    const bodyEl =
      document.querySelector('article.article__bd .article__bd__detail') ||
      document.querySelector('.article__bd__detail') ||
      document.querySelector('.status__main__article');
    const html = bodyEl ? bodyEl.innerHTML : '';
    // 文集索引页特征：很多 <a href="/<uid>/<sid>"> 链接
    const links = Array.from(document.querySelectorAll('a[href*="/2245748859/"]'))
      .map((a) => ({ href: a.getAttribute('href'), text: a.innerText.trim() }))
      .filter((x) => /\/2245748859\/\d{6,}/.test(x.href));
    return { title, date, html, url: location.href, links };
  });

  return data;
}

function htmlToMd(data) {
  const md = td.turndown(data.html || '');
  return `---
source: ${data.url}
fetched: ${new Date().toISOString().slice(0, 10)}
title: ${data.title}
publisher: 雪球
published: ${data.date || ''}
author: 姜诚
verified: partial
---

# ${data.title}

> 发布时间：${data.date || '未抓到'}

${md}
`;
}

async function fetchCommand(arg) {
  const url = statusUrl(arg);
  const sid = parseStatusId(arg.replace(/^.*\//, ''));
  const ctx = await launch(false);
  const page = ctx.pages()[0] ?? (await ctx.newPage());
  const data = await fetchOne(page, url);
  const out = path.join(OUT_DIR, `${sid}.md`);
  fs.writeFileSync(out, htmlToMd(data), 'utf8');
  console.log(`saved: ${out} (${data.html.length} chars HTML)`);
  await ctx.close();
}

async function fetchCollection(rootArg) {
  const rootUrl = statusUrl(rootArg);
  const rootSid = parseStatusId(rootArg.replace(/^.*\//, ''));
  const ctx = await launch(false);
  const page = ctx.pages()[0] ?? (await ctx.newPage());

  // 1. 抓索引页
  const root = await fetchOne(page, rootUrl);
  const idxOut = path.join(OUT_DIR, `${rootSid}_文集索引.md`);
  fs.writeFileSync(idxOut, htmlToMd(root), 'utf8');
  console.log(`索引页已存：${idxOut}`);

  // 2. 提取所有内部链接（去重，去掉自身）
  const seen = new Set();
  const targets = [];
  for (const l of root.links) {
    const m = l.href.match(/\/2245748859\/(\d{6,})/);
    if (!m) continue;
    const sid = m[1];
    if (sid === rootSid) continue;
    if (seen.has(sid)) continue;
    seen.add(sid);
    targets.push({ sid, text: l.text });
  }
  console.log(`索引页提取到 ${targets.length} 篇文章，开始逐篇抓取`);

  // 3. 逐篇抓
  let ok = 0, fail = 0;
  const summary = [];
  for (let i = 0; i < targets.length; i++) {
    const { sid, text } = targets[i];
    const out = path.join(OUT_DIR, `${sid}.md`);
    if (fs.existsSync(out)) {
      console.log(`[${i + 1}/${targets.length}] ${sid} 已存在，跳过`);
      ok++;
      summary.push({ sid, title: text, status: 'skip', file: path.basename(out) });
      continue;
    }
    try {
      const url = `https://xueqiu.com/2245748859/${sid}`;
      const data = await fetchOne(page, url);
      if (!data.html || data.html.length < 200) {
        console.warn(`[${i + 1}/${targets.length}] ${sid} 正文太短(${data.html.length})，可能被拦`);
        fail++;
        summary.push({ sid, title: text, status: 'short', file: '' });
      } else {
        fs.writeFileSync(out, htmlToMd(data), 'utf8');
        console.log(`[${i + 1}/${targets.length}] ${sid} ✓ (${data.html.length} chars) → ${path.basename(out)}`);
        ok++;
        summary.push({ sid, title: data.title, status: 'ok', file: path.basename(out) });
      }
    } catch (e) {
      console.error(`[${i + 1}/${targets.length}] ${sid} ✗ ${e.message}`);
      fail++;
      summary.push({ sid, title: text, status: 'error: ' + e.message, file: '' });
    }
    // 每篇后停 1.5-3s 防风控
    await page.waitForTimeout(1500 + Math.random() * 1500);
  }

  // 4. 写汇总
  const sumPath = path.join(OUT_DIR, '_summary.json');
  fs.writeFileSync(sumPath, JSON.stringify({ root: rootSid, ok, fail, items: summary }, null, 2));
  console.log(`\n完成：成功 ${ok}，失败 ${fail}。汇总：${sumPath}`);
  await ctx.close();
}

// main
const [cmd, ...rest] = process.argv.slice(2);
if (cmd === 'login') {
  await loginFlow();
} else if (cmd === 'fetch') {
  if (!rest[0]) throw new Error('用法: node fetch.mjs fetch <url-or-id>');
  await fetchCommand(rest[0]);
} else if (cmd === 'fetch-collection') {
  if (!rest[0]) throw new Error('用法: node fetch.mjs fetch-collection <url-or-id>');
  await fetchCollection(rest[0]);
} else {
  console.log(`Usage:
  node fetch.mjs login
  node fetch.mjs fetch <url-or-id>
  node fetch.mjs fetch-collection <url-or-id>

例：
  node fetch.mjs login
  node fetch.mjs fetch-collection https://xueqiu.com/2245748859/218571421
`);
}
