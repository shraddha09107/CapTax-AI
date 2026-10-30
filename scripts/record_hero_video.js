/**
 * CapTax AI — 10-Second Screen Recording Generator
 * Uses canvas.captureStream(30) + MediaRecorder in Google Chrome.
 * Produces smooth 10s video/webm screen recordings for both dark and light themes.
 */

import puppeteer from 'puppeteer-core';
import fs from 'fs';
import path from 'path';

const CHROME_PATH = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const OUT_DIR = path.resolve('docs/hero-screenshots');

async function recordTheme(theme, filename) {
  console.log(`\nRecording 10s video for ${theme} theme -> ${filename}...`);
  const browser = await puppeteer.launch({
    executablePath: CHROME_PATH,
    headless: 'new',
    args: [
      '--no-sandbox',
      '--disable-setuid-sandbox',
      '--use-gl=angle',
      '--use-angle=metal',
      '--enable-webgl'
    ]
  });

  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
  await page.goto('http://localhost:8001/', { waitUntil: 'networkidle2' });

  // Set theme
  await page.evaluate((th) => {
    localStorage.setItem('captax-theme', th);
    document.documentElement.setAttribute('data-theme', th);
    document.documentElement.style.colorScheme = th;
    if (window._coinScene) window._coinScene.updateTheme(th);
  }, theme);

  await page.waitForFunction(() => window._coinScene !== undefined, { timeout: 8000 });
  await new Promise((r) => setTimeout(r, 800));

  // Start Canvas MediaRecorder
  await page.evaluate(() => {
    const canvas = document.querySelector('#hero3d canvas');
    if (!canvas) throw new Error('Canvas not found');
    const stream = canvas.captureStream(30);
    const recorder = new MediaRecorder(stream, { mimeType: 'video/webm;codecs=vp9' });
    const chunks = [];
    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) chunks.push(e.data);
    };
    recorder.start(100);
    window._recorder = recorder;
    window._chunks = chunks;
  });

  console.log('  • Recording live frames for 10 seconds...');
  await new Promise((r) => setTimeout(r, 10500));

  // Retrieve base64 encoded webm
  const base64Data = await page.evaluate(async () => {
    return new Promise((resolve) => {
      window._recorder.onstop = () => {
        const blob = new Blob(window._chunks, { type: 'video/webm' });
        const reader = new FileReader();
        reader.onloadend = () => {
          resolve(reader.result.split(',')[1]);
        };
        reader.readAsDataURL(blob);
      };
      window._recorder.stop();
    });
  });

  const buffer = Buffer.from(base64Data, 'base64');
  const dest = path.join(OUT_DIR, filename);
  fs.writeFileSync(dest, buffer);
  console.log(`  ✓ Saved ${filename} (${(buffer.length / 1024).toFixed(1)} KB)`);

  await browser.close();
}

async function main() {
  await recordTheme('dark', 'hero-recording-dark.webm');
  await recordTheme('light', 'hero-recording-light.webm');
  console.log('\n🎉 Both 10-second screen recordings saved successfully!');
}

main().catch((err) => {
  console.error('Recording failed:', err);
  process.exit(1);
});

