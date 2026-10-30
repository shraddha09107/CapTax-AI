/**
 * CapTax AI — Premium 3D Coin Scene (Nickel Quality Bar)
 * High-fidelity PBR metallic coins ($ on front, ₹ on back) traveling along a glowing
 * DTAA arc, flipping at the gate, warming from silver to copper.
 * Procedural studio environment, contact shadows, glass document cards,
 * full-bleed fogged floor, adaptive quality governor, zero interpenetration.
 *
 * Light-Mode v2: copper-gold / graphite-copper palettes, UV-corrected faces,
 * contrast studio environment, slim arc, round particles, right-55% framing.
 */

// Import Three.js locally from vendor bundle (with unpkg fallback)
let THREE;
const VENDOR_THREE = '/static/js/vendor/three.module.js';
const CDN_THREE = 'https://unpkg.com/three@0.158.0/build/three.module.js';

async function loadThree() {
  if (window.THREE) return window.THREE;
  try {
    const mod = await import(VENDOR_THREE);
    return mod;
  } catch {
    const mod = await import(CDN_THREE);
    return mod;
  }
}

// --------------------------------------------------------------------------
// Light-Mode Coin Palettes
// --------------------------------------------------------------------------
const LIGHT_COIN_PALETTES = {
  'copper-gold': {
    fieldBase:    '#E2B07A',
    rimBase:      '#C9743F',
    engravingColor: '#8A4A24',
    edgeReeding:  '#B8693A',
    gateWarm:     '#D9703A',
    brushLines:   'rgba(80, 40, 10, 0.06)',
    radGrad: [
      [0,    '#F5D9A8'],
      [0.25, '#E8B87A'],
      [0.6,  '#C9843F'],
      [1.0,  '#A05A28'],
    ],
    rimGrad: [
      [0,    '#F7D8A0'],
      [0.3,  '#D89050'],
      [0.7,  '#A05A28'],
      [1.0,  '#F0C880'],
    ],
  },
  'graphite-copper': {
    fieldBase:    '#2B2E37',
    rimBase:      '#C9743F',
    engravingColor: '#14161B',
    edgeReeding:  '#3A3D47',
    gateWarm:     '#D9703A',
    brushLines:   'rgba(255,255,255,0.03)',
    radGrad: [
      [0,    '#4A4E5A'],
      [0.35, '#2B2E37'],
      [0.7,  '#1A1D24'],
      [1.0,  '#12141A'],
    ],
    rimGrad: [
      [0,    '#C9743F'],
      [0.3,  '#8A4A24'],
      [0.7,  '#3A3D47'],
      [1.0,  '#C9743F'],
    ],
  },
};

// --------------------------------------------------------------------------
// Procedural High-Res Coin Face Textures (2048×2048)
// --------------------------------------------------------------------------
function createCoinFaceCanvas(symbol, ringText, theme, palette, isFront) {
  const size = 2048;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d');
  const isDark = theme !== 'light';

  // For back face in light mode: mirror horizontally so ₹ reads correctly
  // when viewed from the back (Three.js bottom cap UV mapping needs flip correction)
  if (!isFront && !isDark) {
    ctx.translate(size, 0);
    ctx.scale(-1, 1);
  }

  const cx = size / 2;
  const cy = size / 2;
  const rOuter = size / 2 - 16;
  const rRimInner = rOuter - 80;
  const rBevel = rRimInner - 40;

  // ── Base metallic background ──────────────────────────────────────────────
  if (isDark) {
    ctx.fillStyle = '#D0D5DD';
    ctx.fillRect(0, 0, size, size);
  } else {
    ctx.fillStyle = palette.fieldBase;
    ctx.fillRect(0, 0, size, size);
  }

  ctx.save();
  ctx.beginPath();
  ctx.arc(cx, cy, rOuter, 0, Math.PI * 2);
  ctx.clip();

  // Radial gradient — light field
  const radGrad = ctx.createRadialGradient(cx * 0.7, cy * 0.7, 50, cx, cy, rOuter);
  if (isDark) {
    radGrad.addColorStop(0,    '#FFFFFF');
    radGrad.addColorStop(0.35, '#D8DDE6');
    radGrad.addColorStop(0.7,  '#B8BFCB');
    radGrad.addColorStop(1,    '#98A1B0');
  } else {
    palette.radGrad.forEach(([stop, color]) => radGrad.addColorStop(stop, color));
  }
  ctx.fillStyle = radGrad;
  ctx.fill();

  // Fine circular brush lines
  ctx.lineWidth = 1;
  for (let r = 80; r < rBevel; r += 8) {
    const base = isDark ? 0.015 : 0.04;
    const extra = isDark ? 0.02 : 0.05;
    ctx.strokeStyle = isDark
      ? `rgba(0, 0, 0, ${base + (r % 16 === 0 ? extra : 0)})`
      : palette.brushLines;
    ctx.beginPath();
    ctx.arc(cx, cy, r, 0, Math.PI * 2);
    ctx.stroke();
  }

  // Raised Rim (outer polished ring)
  ctx.lineWidth = 72;
  const rimGrad = ctx.createLinearGradient(0, 0, size, size);
  if (isDark) {
    rimGrad.addColorStop(0,   '#FFFFFF');
    rimGrad.addColorStop(0.3, '#CBD2DC');
    rimGrad.addColorStop(0.7, '#8A93A2');
    rimGrad.addColorStop(1,   '#FFFFFF');
  } else {
    palette.rimGrad.forEach(([stop, color]) => rimGrad.addColorStop(stop, color));
  }
  ctx.strokeStyle = rimGrad;
  ctx.beginPath();
  ctx.arc(cx, cy, rOuter - 36, 0, Math.PI * 2);
  ctx.stroke();

  // Outer bevel shadow
  ctx.lineWidth = 14;
  ctx.strokeStyle = isDark ? 'rgba(0, 0, 0, 0.35)' : 'rgba(60, 30, 5, 0.50)';
  ctx.beginPath();
  ctx.arc(cx, cy, rRimInner, 0, Math.PI * 2);
  ctx.stroke();

  // Outer bevel light glint
  ctx.lineWidth = 6;
  ctx.strokeStyle = isDark ? 'rgba(255,255,255,0.3)' : 'rgba(255,220,160,0.5)';
  ctx.beginPath();
  ctx.arc(cx, cy, rRimInner + 10, 0, Math.PI * 2);
  ctx.stroke();

  // Ring text ("CAPTAX AI • 2026 • …")
  ctx.save();
  ctx.font = 'bold 54px "Plus Jakarta Sans", sans-serif';
  ctx.fillStyle = isDark ? '#4B5563' : (palette.engravingColor + 'CC');
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  const chars = ringText.split('');
  const textRadius = rRimInner - 70;
  const angleStep = (Math.PI * 1.5) / (chars.length - 1);
  const startAngle = Math.PI * 0.25;

  chars.forEach((ch, i) => {
    const angle = startAngle + i * angleStep;
    ctx.save();
    ctx.translate(cx + Math.cos(angle) * textRadius, cy + Math.sin(angle) * textRadius);
    ctx.rotate(angle + Math.PI / 2);
    ctx.fillText(ch, 0, 0);
    ctx.restore();
  });
  ctx.restore();

  // Inner ring bevel
  ctx.lineWidth = 10;
  ctx.strokeStyle = isDark ? 'rgba(255, 255, 255, 0.4)' : 'rgba(255, 200, 120, 0.35)';
  ctx.beginPath();
  ctx.arc(cx, cy, textRadius - 60, 0, Math.PI * 2);
  ctx.stroke();

  // ── Center Currency Symbol ─────────────────────────────────────────────
  // Use a large, heavy font weight. Use system serif fallback for ₹ compatibility.
  const symbolFont = (symbol === '₹')
    ? '900 600px "Noto Sans", "Plus Jakarta Sans", serif'
    : '900 680px "Plus Jakarta Sans", sans-serif';
  ctx.font = symbolFont;
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';

  // Shadow (bottom-right bevel)
  ctx.fillStyle = isDark ? 'rgba(0, 0, 0, 0.45)' : `${palette.engravingColor}99`;
  ctx.fillText(symbol, cx + 16, cy + 20);

  // Highlight (top-left bevel)
  ctx.fillStyle = isDark ? 'rgba(255, 255, 255, 0.7)' : 'rgba(255, 220, 160, 0.65)';
  ctx.fillText(symbol, cx - 12, cy - 14);

  // Main engraved glyph
  const symGrad = ctx.createLinearGradient(cx - 200, cy - 200, cx + 200, cy + 200);
  if (isDark) {
    symGrad.addColorStop(0, '#5A6372');
    symGrad.addColorStop(0.5, '#3D4450');
    symGrad.addColorStop(1, '#1F242C');
  } else {
    symGrad.addColorStop(0, palette.engravingColor + 'EE');
    symGrad.addColorStop(0.5, palette.engravingColor);
    symGrad.addColorStop(1, palette.engravingColor + 'BB');
  }
  ctx.fillStyle = symGrad;
  ctx.fillText(symbol, cx, cy + 4);

  // Glint across glyph
  ctx.save();
  ctx.globalCompositeOperation = 'source-atop';
  const glintGrad = ctx.createLinearGradient(cx - 300, cy - 300, cx + 300, cy + 300);
  glintGrad.addColorStop(0.45, 'rgba(255,255,255,0)');
  glintGrad.addColorStop(0.5, isDark ? 'rgba(255,255,255,0.28)' : 'rgba(255,240,200,0.35)');
  glintGrad.addColorStop(0.55, 'rgba(255,255,255,0)');
  ctx.fillStyle = glintGrad;
  ctx.fillRect(0, 0, size, size);
  ctx.restore();

  ctx.restore();
  return canvas;
}

// --------------------------------------------------------------------------
// Reeded Edge Normal/Bump Map
// --------------------------------------------------------------------------
function createReededEdgeCanvas(theme, palette) {
  const width = 1024;
  const height = 128;
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  const isDark = theme !== 'light';

  ctx.fillStyle = isDark ? '#808080' : palette.edgeReeding;
  ctx.fillRect(0, 0, width, height);

  const grooves = 128;
  const step = width / grooves;
  for (let i = 0; i < grooves; i++) {
    const x = i * step;
    const grad = ctx.createLinearGradient(x, 0, x + step, 0);
    if (isDark) {
      grad.addColorStop(0,   '#FFFFFF');
      grad.addColorStop(0.5, '#202020');
      grad.addColorStop(1,   '#FFFFFF');
    } else {
      grad.addColorStop(0,   '#FFD090');
      grad.addColorStop(0.5, '#6B3510');
      grad.addColorStop(1,   '#FFD090');
    }
    ctx.fillStyle = grad;
    ctx.fillRect(x, 4, step * 0.75, height - 8);
  }
  return canvas;
}

// --------------------------------------------------------------------------
// Glass Card Canvas (2× DPR crispness)
// --------------------------------------------------------------------------
function createGlassCardCanvas(title, subtitle, metricVal, metricSub, theme) {
  const width = 1024;
  const height = 576;
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  const isDark = theme !== 'light';

  // Glass backdrop with soft gradient
  const bgGrad = ctx.createLinearGradient(0, 0, width, height);
  if (isDark) {
    bgGrad.addColorStop(0, 'rgba(24, 27, 36, 0.92)');
    bgGrad.addColorStop(1, 'rgba(14, 16, 22, 0.88)');
  } else {
    bgGrad.addColorStop(0, 'rgba(255, 255, 255, 0.97)');
    bgGrad.addColorStop(1, 'rgba(247, 245, 242, 0.95)');
  }
  ctx.fillStyle = bgGrad;
  if (typeof ctx.roundRect === 'function') {
    ctx.roundRect(8, 8, width - 16, height - 16, 36);
  } else {
    ctx.fillRect(8, 8, width - 16, height - 16);
  }
  ctx.fill();

  // Border
  const strokeGrad = ctx.createLinearGradient(0, 0, width, height);
  if (isDark) {
    strokeGrad.addColorStop(0,   'rgba(255, 255, 255, 0.28)');
    strokeGrad.addColorStop(0.5, 'rgba(240, 80, 45, 0.45)');
    strokeGrad.addColorStop(1,   'rgba(255, 255, 255, 0.08)');
  } else {
    strokeGrad.addColorStop(0,   'rgba(20, 20, 25, 0.12)');
    strokeGrad.addColorStop(0.5, 'rgba(240, 80, 45, 0.25)');
    strokeGrad.addColorStop(1,   'rgba(20, 20, 25, 0.06)');
  }
  ctx.lineWidth = 3;
  ctx.strokeStyle = strokeGrad;
  if (typeof ctx.roundRect === 'function') {
    ctx.roundRect(8, 8, width - 16, height - 16, 36);
  } else {
    ctx.strokeRect(8, 8, width - 16, height - 16);
  }
  ctx.stroke();

  // Brand Mark
  ctx.fillStyle = '#F0502D';
  if (typeof ctx.roundRect === 'function') {
    ctx.roundRect(48, 48, 38, 38, 10);
    ctx.fill();
  } else {
    ctx.fillRect(48, 48, 38, 38);
  }
  ctx.fillStyle = '#FFFFFF';
  ctx.font = '800 24px "Plus Jakarta Sans", sans-serif';
  ctx.fillText('₹', 60, 75);

  ctx.fillStyle = isDark ? '#94A3B8' : '#52525C';
  ctx.font = '700 24px "Plus Jakarta Sans", sans-serif';
  ctx.fillText('CapTax AI', 102, 75);

  // "Sample data" badge
  ctx.fillStyle = isDark ? 'rgba(251, 191, 36, 0.15)' : 'rgba(217, 119, 6, 0.10)';
  if (typeof ctx.roundRect === 'function') {
    ctx.roundRect(width - 240, 48, 190, 36, 18);
    ctx.fill();
  }
  ctx.strokeStyle = isDark ? '#FBBF24' : '#D97706';
  ctx.lineWidth = 2;
  if (typeof ctx.roundRect === 'function') {
    ctx.roundRect(width - 240, 48, 190, 36, 18);
    ctx.stroke();
  }
  ctx.fillStyle = isDark ? '#FBBF24' : '#B45309';
  ctx.font = '700 18px "Plus Jakarta Sans", sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('SAMPLE DATA', width - 145, 72);
  ctx.textAlign = 'left';

  // Card Title
  ctx.fillStyle = isDark ? '#FFFFFF' : '#15151A';
  ctx.font = '800 52px "Plus Jakarta Sans", sans-serif';
  ctx.fillText(title, 48, 175);

  // Card Subtitle
  ctx.fillStyle = isDark ? '#94A3B8' : '#55555F';
  ctx.font = '500 28px "Plus Jakarta Sans", sans-serif';
  ctx.fillText(subtitle, 48, 225);

  // Big Metric
  ctx.fillStyle = isDark ? '#FFFFFF' : '#15151A';
  ctx.font = '800 68px "Plus Jakarta Sans", sans-serif';
  ctx.fillText(metricVal, 48, 340);

  // Metric sub-label
  ctx.fillStyle = isDark ? '#3DDC97' : '#12A150';
  ctx.font = '600 26px "Plus Jakarta Sans", sans-serif';
  ctx.fillText(metricSub, 48, 385);

  // Mini Chart Bars
  const bars = [0.35, 0.65, 0.45, 0.85, 0.6, 0.95, 0.75, 1.0];
  const barW = 28;
  const barGap = 16;
  const startX = width - (bars.length * (barW + barGap) + 48);
  const baseH = 460;

  bars.forEach((h, i) => {
    const bh = h * 120;
    const x = startX + i * (barW + barGap);
    const isHighlight = i === bars.length - 1;
    ctx.fillStyle = isHighlight
      ? '#F0502D'
      : (isDark ? 'rgba(255, 255, 255, 0.18)' : 'rgba(20, 20, 25, 0.12)');
    if (typeof ctx.roundRect === 'function') {
      ctx.roundRect(x, baseH - bh, barW, bh, 8);
    } else {
      ctx.fillRect(x, baseH - bh, barW, bh);
    }
    ctx.fill();
  });

  // Light-mode soft shadow strip at bottom
  if (!isDark) {
    const shadowGrad = ctx.createLinearGradient(0, height - 40, 0, height);
    shadowGrad.addColorStop(0, 'rgba(20,20,25,0)');
    shadowGrad.addColorStop(1, 'rgba(20,20,25,0.04)');
    ctx.fillStyle = shadowGrad;
    ctx.fillRect(0, height - 40, width, 40);
  }

  return canvas;
}

// --------------------------------------------------------------------------
// Perspective Floor Grid Canvas
// --------------------------------------------------------------------------
function createFloorGridCanvas(theme) {
  const size = 1024;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d');
  const isDark = theme !== 'light';

  ctx.fillStyle = isDark ? '#0c0c0e' : '#F3F1EE';
  ctx.fillRect(0, 0, size, size);

  // Subtle studio grid lines
  const gridColor = isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(20, 20, 25, 0.04)';
  ctx.strokeStyle = gridColor;
  ctx.lineWidth = 2;

  const step = 64;
  for (let i = 0; i <= size; i += step) {
    ctx.beginPath();
    ctx.moveTo(i, 0);
    ctx.lineTo(i, size);
    ctx.stroke();

    ctx.beginPath();
    ctx.moveTo(0, i);
    ctx.lineTo(size, i);
    ctx.stroke();
  }

  return canvas;
}

// --------------------------------------------------------------------------
// Round Sprite Texture for Particles
// --------------------------------------------------------------------------
function createParticleSpriteCanvas(theme) {
  const size = 64;
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext('2d');

  const grad = ctx.createRadialGradient(32, 32, 0, 32, 32, 30);
  if (theme !== 'light') {
    grad.addColorStop(0,    'rgba(240, 180, 100, 1.0)');
    grad.addColorStop(0.4,  'rgba(240, 100, 45, 0.7)');
    grad.addColorStop(1.0,  'rgba(240, 80, 45, 0)');
  } else {
    // Warm copper-gold dust for light mode
    grad.addColorStop(0,    'rgba(210, 140, 60, 1.0)');
    grad.addColorStop(0.45, 'rgba(190, 100, 40, 0.6)');
    grad.addColorStop(1.0,  'rgba(180, 80, 30, 0)');
  }
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);

  return canvas;
}

// --------------------------------------------------------------------------
// Procedural Studio Environment Generator (PMREM)
// --------------------------------------------------------------------------
function buildStudioEnvironment(THREE, pmremGenerator, theme) {
  const envScene = new THREE.Scene();
  const isDark = theme !== 'light';

  // Gradient dome background
  const domeGeo = new THREE.SphereGeometry(15, 32, 16);
  const domeMat = new THREE.MeshBasicMaterial({
    color: isDark ? 0x05070A : 0xD8D5CF,
    side: THREE.BackSide,
  });
  envScene.add(new THREE.Mesh(domeGeo, domeMat));

  // Key Softbox light (large emissive rectangular panel, upper-left front)
  const keySoftbox = new THREE.Mesh(
    new THREE.PlaneGeometry(8, 5),
    new THREE.MeshBasicMaterial({ color: isDark ? 0xF0F4FF : 0xFFFFFF })
  );
  keySoftbox.position.set(-6, 7, 5);
  keySoftbox.lookAt(0, 0, 0);
  envScene.add(keySoftbox);

  // Fill Softbox (cooler tone, upper-right front)
  const fillSoftbox = new THREE.Mesh(
    new THREE.PlaneGeometry(6, 4),
    new THREE.MeshBasicMaterial({ color: isDark ? 0x90B4E0 : 0xE8E4DC })
  );
  fillSoftbox.position.set(7, 6, 4);
  fillSoftbox.lookAt(0, 0, 0);
  envScene.add(fillSoftbox);

  // Rim / Accent light (warm orange from back-right)
  const rimStrip = new THREE.Mesh(
    new THREE.PlaneGeometry(4, 9),
    new THREE.MeshBasicMaterial({ color: isDark ? 0xF0502D : 0xC9743F })
  );
  rimStrip.position.set(6, 3, -6);
  rimStrip.lookAt(0, 0, 0);
  envScene.add(rimStrip);

  // Overhead ceiling soft strips
  const ceilingStrip1 = new THREE.Mesh(
    new THREE.PlaneGeometry(12, 1.5),
    new THREE.MeshBasicMaterial({ color: 0xFFFFFF })
  );
  ceilingStrip1.position.set(0, 9, 0);
  ceilingStrip1.rotation.x = Math.PI / 2;
  envScene.add(ceilingStrip1);

  if (!isDark) {
    // === Light theme: dark contrast flags give coins deep, crisp reflections ===

    // Large dark flag — left side (the most important one for metal depth)
    const flagLeft = new THREE.Mesh(
      new THREE.PlaneGeometry(8, 12),
      new THREE.MeshBasicMaterial({ color: 0x0A0B0E })
    );
    flagLeft.position.set(-9, 2, -1);
    flagLeft.lookAt(0, 1, 0);
    envScene.add(flagLeft);

    // Dark flag — right side (creates opposite edge contrast)
    const flagRight = new THREE.Mesh(
      new THREE.PlaneGeometry(6, 10),
      new THREE.MeshBasicMaterial({ color: 0x181A20 })
    );
    flagRight.position.set(9, 2, -1);
    flagRight.lookAt(0, 1, 0);
    envScene.add(flagRight);

    // Mid-dark flag — behind the scene (depth in reflection)
    const flagBack = new THREE.Mesh(
      new THREE.PlaneGeometry(14, 8),
      new THREE.MeshBasicMaterial({ color: 0x141720 })
    );
    flagBack.position.set(0, 0, -8);
    envScene.add(flagBack);

    // Thin bright top strip (specular glint line)
    const topStrip = new THREE.Mesh(
      new THREE.PlaneGeometry(16, 0.8),
      new THREE.MeshBasicMaterial({ color: 0xFFFFFF })
    );
    topStrip.position.set(0, 8, 2);
    topStrip.rotation.x = Math.PI * 0.15;
    envScene.add(topStrip);

    // Warm bounce from below (simulated warm floor reflection)
    const bottomBounce = new THREE.Mesh(
      new THREE.PlaneGeometry(10, 4),
      new THREE.MeshBasicMaterial({ color: 0xF0C880 })
    );
    bottomBounce.position.set(0, -4, 3);
    bottomBounce.rotation.x = -Math.PI * 0.25;
    envScene.add(bottomBounce);
  }

  const renderTarget = pmremGenerator.fromScene(envScene, 0.04);
  envScene.traverse((obj) => {
    if (obj.geometry) obj.geometry.dispose();
    if (obj.material) obj.material.dispose();
  });

  return renderTarget.texture;
}

// --------------------------------------------------------------------------
// UV Remapping helper — correct glyph orientation on both caps
// --------------------------------------------------------------------------
function remapCoinCapUVs(geo) {
  const R_COIN = 0.55;
  const pos = geo.attributes.position;
  const uv = geo.attributes.uv;
  const idx = geo.index;

  const g1 = geo.groups[1]; // Top cap (+Z front face $)
  const g2 = geo.groups[2]; // Bottom cap (-Z back face ₹)

  // Top cap: u = (x / 2R + 0.5), v = (y / 2R + 0.5)  ← normal orientation
  const g1Verts = new Set();
  for (let i = g1.start; i < g1.start + g1.count; i++) g1Verts.add(idx.getX(i));
  for (const v of g1Verts) {
    const x = pos.getX(v);
    const y = pos.getY(v);
    uv.setXY(v, (x / (2 * R_COIN)) + 0.5, (y / (2 * R_COIN)) + 0.5);
  }

  // Bottom cap: flip X so ₹ is NOT mirrored when viewed from outside.
  // u = (-x / 2R + 0.5), v = (y / 2R + 0.5)
  const g2Verts = new Set();
  for (let i = g2.start; i < g2.start + g2.count; i++) g2Verts.add(idx.getX(i));
  for (const v of g2Verts) {
    const x = pos.getX(v);
    const y = pos.getY(v);
    uv.setXY(v, (-x / (2 * R_COIN)) + 0.5, (y / (2 * R_COIN)) + 0.5);
  }

  uv.needsUpdate = true;
}

// --------------------------------------------------------------------------
// Splines & Collision-Free Lanes
// --------------------------------------------------------------------------
const R = 0.55;
const THICKNESS = 0.09;
const FLOOR_Y = -1.5;

// Lanes shifted to right half: X range roughly [0, 7] instead of [-6.5, 6.5]
// to sit in the right ~55% of the viewport when camera is at X~2
const LANES = [
  // Lane 0: Deep Foreground (Z = +1.9)
  [
    [-1.5,  0.2, 1.9],
    [ 1.2,  1.4, 1.9],
    [ 3.8,  2.1, 1.9],
    [ 6.0,  1.2, 1.9],
    [ 8.0, -0.1, 1.9]
  ],
  // Lane 1: Mid-Foreground (Z = +0.6)
  [
    [-1.2,  0.5, 0.6],
    [ 1.4,  1.8, 0.6],
    [ 4.0,  2.6, 0.6],
    [ 6.2,  1.6, 0.6],
    [ 8.2,  0.3, 0.6]
  ],
  // Lane 2: Hero Gate Lane (Z = -0.7) — gate at X ~ 3.5
  [
    [-1.0,  0.8, -0.7],
    [ 1.5,  2.2, -0.7],
    [ 3.5,  2.9, -0.7],
    [ 6.0,  2.0, -0.7],
    [ 8.0,  0.6, -0.7]
  ],
  // Lane 3: Mid-Background (Z = -2.0)
  [
    [-1.2,  0.3, -2.0],
    [ 1.2,  1.5, -2.0],
    [ 3.5,  2.3, -2.0],
    [ 5.8,  1.3, -2.0],
    [ 7.8,  0.1, -2.0]
  ],
  // Lane 4: Upper Background (Z = -3.2)
  [
    [-1.5,  1.0, -3.2],
    [ 1.0,  2.4, -3.2],
    [ 3.5,  3.2, -3.2],
    [ 6.0,  2.2, -3.2],
    [ 7.8,  0.8, -3.2]
  ]
];

function evalLane(laneIdx, u) {
  const pts = LANES[laneIdx];
  const n = pts.length - 1;
  const clamped = Math.max(0, Math.min(1, u));
  const p = clamped * n;
  const idx = Math.min(Math.floor(p), n - 1);
  const t = p - idx;

  const p0 = pts[Math.max(0, idx - 1)];
  const p1 = pts[idx];
  const p2 = pts[Math.min(n, idx + 1)];
  const p3 = pts[Math.min(n, idx + 2)];

  const t2 = t * t;
  const t3 = t2 * t;

  return [
    0.5 * ((2 * p1[0]) + (-p0[0] + p2[0]) * t + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2 + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3),
    0.5 * ((2 * p1[1]) + (-p0[1] + p2[1]) * t + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2 + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3),
    0.5 * ((2 * p1[2]) + (-p0[2] + p2[2]) * t + (2 * p0[2] - 5 * p1[2] + 4 * p2[2] - p3[2]) * t2 + (-p0[2] + 3 * p1[2] - 3 * p2[2] + p3[2]) * t3)
  ];
}

// Cards shifted right as well
const CARDS_DATA = [
  { title: 'Schedule CG',  sub: 'Capital Gains • FIFO', val: '₹1.32 Cr', change: '+14.2% YoY', pos: [ 1.0, 0.9, -0.1], half: [1.1, 0.65, 0.15] },
  { title: 'Schedule FSI', sub: 'Foreign Dividends • DTAA', val: '$24,850', change: '25% Relief Capped', pos: [ 3.5, 1.4, -1.35], half: [1.1, 0.65, 0.15] },
  { title: 'Form 67',      sub: 'Tax Credit Statement', val: '₹4.82 L', change: 'Audit Ready', pos: [ 6.0, 0.8, -0.1], half: [1.1, 0.65, 0.15] }
];

const STATIC_COIN_DEFS = [
  { pos: [ 1.5, FLOOR_Y + THICKNESS / 2,  1.0], rot: [Math.PI / 2, 0, 0.4], isRupee: false },
  { pos: [ 3.0, FLOOR_Y + THICKNESS / 2,  0.5], rot: [Math.PI / 2, 0, -0.2], isRupee: false },
  { pos: [ 4.5, FLOOR_Y + THICKNESS / 2,  1.1], rot: [Math.PI / 2, Math.PI, 0.6], isRupee: true },
  { pos: [ 6.0, FLOOR_Y + THICKNESS / 2,  0.6], rot: [Math.PI / 2, Math.PI, -0.3], isRupee: true }
];

// Gate position matches hero lane (Lane 2 midpoint)
const GATE_POS = [3.5, 2.9, -0.7];

// --------------------------------------------------------------------------
// Debug Face View — renders two static coins for face inspection
// --------------------------------------------------------------------------
function renderDebugFaces(THREE, scene, coinGeo, matFront, matBack, matEdge) {
  const mats = [matEdge, matFront, matBack];

  // Front coin ($)
  const coinFront = new THREE.Mesh(coinGeo, mats);
  coinFront.position.set(-2.0, 0, 0);
  coinFront.rotation.set(0, 0, 0); // Face toward camera (+Z)
  scene.add(coinFront);

  // Back coin (₹) — rotated 180° around Y so back face faces camera
  const coinBack = new THREE.Mesh(coinGeo, mats);
  coinBack.position.set(2.0, 0, 0);
  coinBack.rotation.set(0, Math.PI, 0); // Rotated to show back face
  scene.add(coinBack);

  // Labels
  // (labels would need HTML overlay, skip in 3D)
  return [coinFront, coinBack];
}

// --------------------------------------------------------------------------
// MAIN COIN SCENE INITIALIZER
// --------------------------------------------------------------------------
export async function initCoinScene(container, { theme = 'dark' } = {}) {
  // Check URL parameters
  const urlParams = new URLSearchParams(window.location.search);
  const frozenTimeParam = urlParams.get('t');
  const isTimeFrozen = frozenTimeParam !== null;
  const frozenTime = parseFloat(frozenTimeParam || '0');
  const isDebugCollisions = urlParams.get('debug') === 'collisions';
  const isDebugFaces = urlParams.get('debug') === 'faces';

  // Light coin palette selection
  const lightCoinParam = urlParams.get('lightCoin') || 'copper-gold';
  const lightPalette = LIGHT_COIN_PALETTES[lightCoinParam] || LIGHT_COIN_PALETTES['copper-gold'];

  // Load Three.js
  THREE = await loadThree();
  if (!THREE) {
    console.warn('[CoinScene] Three.js could not be loaded.');
    return null;
  }

  // WebGL support check
  try {
    const testCanvas = document.createElement('canvas');
    const gl = testCanvas.getContext('webgl2') || testCanvas.getContext('webgl');
    if (!gl) throw new Error('No WebGL');
  } catch {
    console.warn('[CoinScene] WebGL unavailable.');
    return null;
  }

  const isMobile = window.innerWidth < 768;
  const isDark = theme !== 'light';

  // Resolution & DPR cap (2.0 desktop, 1.5 mobile)
  const dpr = Math.min(window.devicePixelRatio || 1, isMobile ? 1.5 : 2.0);

  // WebGLRenderer
  const renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: true,
    powerPreference: 'high-performance',
    stencil: false
  });
  renderer.setPixelRatio(dpr);
  renderer.setSize(container.clientWidth, container.clientHeight);
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  // Light mode: lower exposure so highlights don't clip
  renderer.toneMappingExposure = isDark ? 1.25 : 0.95;
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.shadowMap.enabled = true;
  renderer.shadowMap.type = THREE.PCFSoftShadowMap;

  container.innerHTML = '';
  container.appendChild(renderer.domElement);

  // Scene & Camera
  const scene = new THREE.Scene();

  // Camera framing: right ~55% of viewport
  // In light mode, shift camera target to X ~2.5 so coins occupy the right side
  const camTargetX = isDark ? 0 : 2.5;
  const camPosX    = isDark ? 0 : 2.0;

  const camera = new THREE.PerspectiveCamera(40, container.clientWidth / container.clientHeight, 0.1, 100);
  camera.position.set(camPosX, 1.5, 10.5);
  camera.lookAt(camTargetX, 1.2, 0);

  // Procedural Studio Environment
  const pmremGenerator = new THREE.PMREMGenerator(renderer);
  pmremGenerator.compileEquirectangularShader();
  let currentEnvTexture = buildStudioEnvironment(THREE, pmremGenerator, theme);
  scene.environment = currentEnvTexture;

  // Fog — in light mode only fog the far floor, not foreground/mid-ground coins
  const bgAppColor = isDark ? 0x0c0c0e : 0xF3F1EE;
  if (isDark) {
    scene.fog = new THREE.Fog(bgAppColor, 8, 26);
  } else {
    // Start fog much farther away so coins stay crisp
    scene.fog = new THREE.Fog(bgAppColor, 18, 38);
  }

  // Studio Lighting
  const ambientLight = new THREE.AmbientLight(
    isDark ? 0x222834 : 0xF5E8D0,
    isDark ? 1.2 : 1.0
  );
  scene.add(ambientLight);

  const keyLight = new THREE.DirectionalLight(0xFFFFFF, isDark ? 2.8 : 1.8);
  keyLight.position.set(-6, 8, 7);
  keyLight.castShadow = true;
  keyLight.shadow.mapSize.set(2048, 2048);
  keyLight.shadow.bias = -0.0001;
  keyLight.shadow.radius = 3;
  scene.add(keyLight);

  const orangeRimLight = new THREE.DirectionalLight(0xF0502D, isDark ? 2.5 : 1.2);
  orangeRimLight.position.set(7, 4, -5);
  scene.add(orangeRimLight);

  // Warm orange rim glint for light mode — thin edge catch from back-right
  const warmRimLight = new THREE.DirectionalLight(0xD9703A, isDark ? 0 : 0.85);
  warmRimLight.position.set(5, 2, -8);
  scene.add(warmRimLight);

  const fillLight = new THREE.PointLight(
    isDark ? 0x4D88FF : 0xE8C89A,
    isDark ? 1.4 : 0.6,
    25
  );
  fillLight.position.set(-5, 0, 4);
  scene.add(fillLight);

  // ------------------------------------------------------------------------
  // High-Resolution PBR Materials & Textures
  // ------------------------------------------------------------------------
  const maxAnisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 16);

  // Front Face ($) — isFront=true means NO horizontal flip on canvas
  const dollarCanvas = createCoinFaceCanvas('$', 'CAPTAX AI • 2026 • US ASSET', theme, lightPalette, true);
  const dollarTex = new THREE.CanvasTexture(dollarCanvas);
  dollarTex.anisotropy = maxAnisotropy;

  // Back Face (₹) — isFront=false applies horizontal canvas mirror
  const rupeeCanvas = createCoinFaceCanvas('₹', 'CAPTAX AI • 2026 • DTAA RELIEF', theme, lightPalette, false);
  const rupeeTex = new THREE.CanvasTexture(rupeeCanvas);
  rupeeTex.anisotropy = maxAnisotropy;

  // Reeded edge
  const reededCanvas = createReededEdgeCanvas(theme, lightPalette);
  const reededTex = new THREE.CanvasTexture(reededCanvas);
  reededTex.wrapS = THREE.RepeatWrapping;
  reededTex.repeat.set(1, 1);
  reededTex.anisotropy = maxAnisotropy;

  // Coin Geometry — 64 segments for smooth edge
  const coinGeo = new THREE.CylinderGeometry(R, R, THICKNESS, 64);
  coinGeo.rotateX(Math.PI / 2); // Orient so group 1 (+Y cap) → +Z (front)

  // Fix UV mapping for both caps so glyphs are correctly oriented
  remapCoinCapUVs(coinGeo);

  // Light mode coin material params
  const lightMetal  = isDark ? 0.98  : 1.0;
  const lightRough  = isDark ? 0.24  : 0.28;
  const lightEnvInt = isDark ? 1.6   : 1.7;

  // Apply palette tint to base color in light mode
  const fieldColor = isDark
    ? new THREE.Color(1, 1, 1)
    : new THREE.Color(lightPalette.fieldBase);
  const rimColor = isDark
    ? new THREE.Color(1, 1, 1)
    : new THREE.Color(lightPalette.rimBase);

  // Front Material ($)
  const matFront = new THREE.MeshPhysicalMaterial({
    map: dollarTex,
    color: fieldColor,
    metalness: lightMetal,
    roughness: lightRough,
    clearcoat: 0.3,
    clearcoatRoughness: 0.12,
    envMapIntensity: lightEnvInt
  });

  // Back Material (₹)
  const matBack = new THREE.MeshPhysicalMaterial({
    map: rupeeTex,
    color: fieldColor,
    metalness: lightMetal,
    roughness: lightRough,
    clearcoat: 0.3,
    clearcoatRoughness: 0.12,
    envMapIntensity: lightEnvInt
  });

  // Reeded Edge Material
  const matEdge = new THREE.MeshPhysicalMaterial({
    color: rimColor,
    bumpMap: reededTex,
    bumpScale: 0.05,
    metalness: lightMetal,
    roughness: isDark ? 0.18 : 0.15,
    clearcoat: 0.25,
    envMapIntensity: isDark ? 1.5 : 1.6
  });

  const coinMaterials = [matEdge, matFront, matBack];

  // ------------------------------------------------------------------------
  // Floor with Perspective Grid & Fog Blend
  // ------------------------------------------------------------------------
  const floorGridTex = new THREE.CanvasTexture(createFloorGridCanvas(theme));
  floorGridTex.wrapS = floorGridTex.wrapT = THREE.RepeatWrapping;
  floorGridTex.repeat.set(16, 16);

  const floorGeo = new THREE.PlaneGeometry(120, 120);
  const floorMat = new THREE.MeshPhysicalMaterial({
    map: floorGridTex,
    color: bgAppColor,
    roughness: isDark ? 0.35 : 0.55,
    metalness: 0.05,
    clearcoat: isDark ? 0.25 : 0.15,
    clearcoatRoughness: 0.4
  });
  const floorMesh = new THREE.Mesh(floorGeo, floorMat);
  floorMesh.rotation.x = -Math.PI / 2;
  floorMesh.position.y = FLOOR_Y;
  floorMesh.receiveShadow = true;
  scene.add(floorMesh);

  // Soft Contact Shadows for Floor
  const contactShadowTex = (() => {
    const c = document.createElement('canvas');
    c.width = c.height = 256;
    const ctx = c.getContext('2d');
    const grad = ctx.createRadialGradient(128, 128, 10, 128, 128, 120);
    // Warm shadow tint in light mode
    if (isDark) {
      grad.addColorStop(0, 'rgba(0, 0, 0, 0.7)');
      grad.addColorStop(0.5, 'rgba(0, 0, 0, 0.25)');
    } else {
      grad.addColorStop(0, 'rgba(80, 40, 10, 0.35)');
      grad.addColorStop(0.5, 'rgba(60, 30, 8, 0.12)');
    }
    grad.addColorStop(1, 'rgba(0, 0, 0, 0)');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, 256, 256);
    return new THREE.CanvasTexture(c);
  })();

  const contactShadowGeo = new THREE.PlaneGeometry(1.6, 1.6);
  const contactShadowMat = new THREE.MeshBasicMaterial({
    map: contactShadowTex,
    transparent: true,
    opacity: isDark ? 0.6 : 0.30,
    depthWrite: false
  });

  // ------------------------------------------------------------------------
  // DTAA Arc Tube & Portal Gate — slim version in light mode
  // ------------------------------------------------------------------------
  const arcCurve = new THREE.CatmullRomCurve3([
    new THREE.Vector3(-1.5, 0.4, 0.0),
    new THREE.Vector3( 1.0, 2.0, 0.0),
    new THREE.Vector3( 3.5, 2.9, 0.0),
    new THREE.Vector3( 6.0, 1.8, 0.0),
    new THREE.Vector3( 8.2, 0.3, 0.0)
  ]);

  // Slim tube: ~1/3 of old thickness in light mode
  const arcRadius = isDark ? 0.045 : 0.016;
  const arcTubeGeo = new THREE.TubeGeometry(arcCurve, 80, arcRadius, 10, false);
  const arcTubeMat = new THREE.MeshStandardMaterial({
    color: 0xF0502D,
    emissive: 0xF0502D,
    emissiveIntensity: isDark ? 2.0 : 0.9,
    roughness: isDark ? 0.2 : 0.15,
    metalness: 0.5
  });
  const arcMesh = new THREE.Mesh(arcTubeGeo, arcTubeMat);
  scene.add(arcMesh);

  // DTAA Gate Ring at gate position
  const gateTorusGeo = new THREE.TorusGeometry(0.9, isDark ? 0.04 : 0.022, 16, 48);
  const gateTorusMat = new THREE.MeshStandardMaterial({
    color: 0xF0502D,
    emissive: 0xF0502D,
    emissiveIntensity: isDark ? 2.5 : 1.0,
    roughness: 0.2
  });
  const gateRing = new THREE.Mesh(gateTorusGeo, gateTorusMat);
  gateRing.position.set(GATE_POS[0], GATE_POS[1], GATE_POS[2]);
  gateRing.rotation.y = Math.PI / 2;
  scene.add(gateRing);

  // Traveling Light Pulse on Arc
  const pulseGeo = new THREE.SphereGeometry(0.10, 16, 16);
  const pulseMat = new THREE.MeshBasicMaterial({
    color: isDark ? 0xFFFFFF : 0xF0A060
  });
  const pulseMesh = new THREE.Mesh(pulseGeo, pulseMat);
  scene.add(pulseMesh);

  // Sparkle Particles — round soft sprites
  const SPARKLE_COUNT = 24;
  const sparkleGeo = new THREE.BufferGeometry();
  const sparklePos = new Float32Array(SPARKLE_COUNT * 3);
  for (let i = 0; i < SPARKLE_COUNT; i++) {
    sparklePos[i * 3 + 0] = GATE_POS[0] + (Math.random() - 0.5) * 1.5;
    sparklePos[i * 3 + 1] = GATE_POS[1] + (Math.random() - 0.5) * 1.5;
    sparklePos[i * 3 + 2] = GATE_POS[2] + (Math.random() - 0.5) * 1.5;
  }
  sparkleGeo.setAttribute('position', new THREE.BufferAttribute(sparklePos, 3));

  const particleSpriteCanvas = createParticleSpriteCanvas(theme);
  const particleSpriteTex = new THREE.CanvasTexture(particleSpriteCanvas);

  const sparkleMat = new THREE.PointsMaterial({
    map: particleSpriteTex,
    color: isDark ? 0xF0B050 : 0xD08030,
    size: isDark ? 0.10 : 0.08,
    transparent: true,
    opacity: isDark ? 0.85 : 0.70,
    sizeAttenuation: true,
    alphaTest: 0.01,
    depthWrite: false
  });
  const sparklePoints = new THREE.Points(sparkleGeo, sparkleMat);
  scene.add(sparklePoints);

  // ------------------------------------------------------------------------
  // Floating Glass Cards (Schedule CG, Schedule FSI, Form 67)
  // Uses MeshBasicMaterial for crisp text — not washed out by lighting
  // ------------------------------------------------------------------------
  const cardMeshes = [];
  CARDS_DATA.forEach((cData, i) => {
    const cardCanvas = createGlassCardCanvas(cData.title, cData.sub, cData.val, cData.change, theme);
    const cardTex = new THREE.CanvasTexture(cardCanvas);
    cardTex.anisotropy = maxAnisotropy;

    const cGeo = new THREE.PlaneGeometry(cData.half[0] * 2, cData.half[1] * 2);

    // MeshBasicMaterial: immune to lighting → text is always crisp & readable
    const cMat = new THREE.MeshBasicMaterial({
      map: cardTex,
      transparent: true,
      opacity: isDark ? 0.94 : 0.96,
      side: THREE.DoubleSide,
      depthWrite: false
    });

    const cMesh = new THREE.Mesh(cGeo, cMat);
    cMesh.position.set(...cData.pos);
    cMesh.castShadow = false;
    scene.add(cMesh);

    cardMeshes.push({
      mesh: cMesh,
      basePos: [...cData.pos],
      phase: i * 2.1
    });
  });

  // ------------------------------------------------------------------------
  // Debug Face View (renders before normal coins)
  // ------------------------------------------------------------------------
  if (isDebugFaces) {
    // Clear lanes, just show two big coins face-on
    const debugFaceCoins = renderDebugFaces(THREE, scene, coinGeo, matFront, matBack, matEdge);

    // Position camera to look at both
    camera.position.set(0, 0, 5);
    camera.lookAt(0, 0, 0);
    scene.fog = null;

    // Bright direct light for face inspection
    const debugLight = new THREE.DirectionalLight(0xFFFFFF, 3.0);
    debugLight.position.set(0, 2, 6);
    scene.add(debugLight);

    updateScene(0);
    renderer.render(scene, camera);
    return { updateTheme: () => {}, togglePause: () => false, destroy: () => {} };
  }

  // ------------------------------------------------------------------------
  // Coin Instances & Dynamic InstancedMesh
  // ------------------------------------------------------------------------
  const DYNAMIC_COUNT = isMobile ? 10 : 20;
  const TOTAL_COINS = DYNAMIC_COUNT + 4; // plus 4 static coins on floor

  const coinMeshes = [];
  const shadowMeshes = [];

  // Create individual coin meshes using shared geometry & materials
  for (let i = 0; i < TOTAL_COINS; i++) {
    const mesh = new THREE.Mesh(coinGeo, coinMaterials);
    mesh.castShadow = true;
    mesh.receiveShadow = true;
    scene.add(mesh);
    coinMeshes.push(mesh);

    // Associated contact shadow on floor
    const shadow = new THREE.Mesh(contactShadowGeo, contactShadowMat.clone());
    shadow.rotation.x = -Math.PI / 2;
    shadow.position.y = FLOOR_Y + 0.003;
    scene.add(shadow);
    shadowMeshes.push(shadow);
  }

  // Pre-calculate coin lane configurations (5 lanes * 4 coins = 20)
  const coinConfigs = [];
  let cfgId = 0;
  for (let lane = 0; lane < LANES.length; lane++) {
    const countInLane = isMobile ? 2 : 4;
    for (let c = 0; c < countInLane; c++) {
      coinConfigs.push({
        id: cfgId++,
        lane,
        phaseOffset: c / countInLane,
        loopDuration: 16.0,
        bobSpeed: 1.2,
        bobAmp: 0.04
      });
    }
  }

  // Debug Collision Spheres
  let debugGroup = null;
  if (isDebugCollisions) {
    debugGroup = new THREE.Group();
    const sphereGeo = new THREE.SphereGeometry(R, 16, 16);
    const sphereMat = new THREE.MeshBasicMaterial({ color: 0x00FF88, wireframe: true });
    for (let i = 0; i < TOTAL_COINS; i++) {
      const s = new THREE.Mesh(sphereGeo, sphereMat);
      debugGroup.add(s);
    }
    scene.add(debugGroup);

    // Live debug overlay HUD
    const hud = document.createElement('div');
    hud.id = 'collisionDebugHud';
    hud.style.position = 'fixed';
    hud.style.top = '80px';
    hud.style.left = '20px';
    hud.style.background = 'rgba(0,0,0,0.85)';
    hud.style.color = '#00FF88';
    hud.style.fontFamily = 'monospace';
    hud.style.fontSize = '12px';
    hud.style.padding = '8px 12px';
    hud.style.borderRadius = '6px';
    hud.style.zIndex = '9999';
    document.body.appendChild(hud);
  }

  // Pointer & Scroll Parallax
  const pointer = { x: 0, y: 0, targetX: 0, targetY: 0 };
  let scrollProgress = 0;

  const onPointerMove = (e) => {
    const rect = container.getBoundingClientRect();
    pointer.targetX = ((e.clientX - rect.left) / rect.width - 0.5) * 0.06;
    pointer.targetY = ((e.clientY - rect.top) / rect.height - 0.5) * 0.04;
  };
  const onTouchMove = (e) => {
    if (e.touches[0]) {
      const rect = container.getBoundingClientRect();
      pointer.targetX = ((e.touches[0].clientX - rect.left) / rect.width - 0.5) * 0.04;
      pointer.targetY = ((e.touches[0].clientY - rect.top) / rect.height - 0.5) * 0.03;
    }
  };
  window.addEventListener('mousemove', onPointerMove, { passive: true });
  window.addEventListener('touchmove', onTouchMove, { passive: true });

  const onScroll = () => {
    scrollProgress = Math.min(1, Math.max(0, window.scrollY / window.innerHeight));
  };
  window.addEventListener('scroll', onScroll, { passive: true });

  // Resize handler
  const onResize = () => {
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
  };
  window.addEventListener('resize', onResize);

  // Pause / Play toggle state
  let isPausedByUser = false;
  let isVisible = true;
  const observer = new IntersectionObserver(([entry]) => {
    isVisible = entry.isIntersecting;
  }, { threshold: 0.05 });
  observer.observe(container);

  // Colors for Silver/Gold -> Copper transition
  const colorSilver = isDark
    ? new THREE.Color(0xD0D5DC)
    : new THREE.Color(lightPalette.fieldBase);
  const colorCopper = new THREE.Color(isDark ? 0xE06838 : lightPalette.gateWarm);

  // ------------------------------------------------------------------------
  // Frame Update Routine
  // ------------------------------------------------------------------------
  const clock = new THREE.Clock();
  let rafId = null;

  // Adaptive Quality Governor
  let frameCount = 0;
  let lastTimeCheck = performance.now();
  let fps = 60;
  let currentDprStep = dpr;

  function updateScene(timeSeconds) {
    // 1. Damped Camera Parallax + Scroll Dolly
    pointer.x += (pointer.targetX - pointer.x) * 0.06;
    pointer.y += (pointer.targetY - pointer.y) * 0.06;

    const basePosX = isDark ? 0 : 2.0;
    const baseLookX = isDark ? 0 : 2.5;

    camera.position.x = basePosX + pointer.x * 3.5;
    camera.position.y = 1.5 + pointer.y * 2.0 - scrollProgress * 1.5;
    camera.position.z = 10.5 + scrollProgress * 3.0;
    camera.lookAt(baseLookX, 1.2 - scrollProgress * 0.8, 0);

    // 2. Animate Cards gently
    cardMeshes.forEach(({ mesh, basePos, phase }) => {
      mesh.position.y = basePos[1] + Math.sin(timeSeconds * 0.8 + phase) * 0.08;
      mesh.rotation.y = Math.sin(timeSeconds * 0.4 + phase) * 0.04;
      mesh.rotation.x = Math.cos(timeSeconds * 0.5 + phase) * 0.02;
    });

    // 3. Pulse along Arc Tube
    const pulseU = (timeSeconds * 0.4) % 1.0;
    const pulsePos = arcCurve.getPointAt(pulseU);
    pulseMesh.position.copy(pulsePos);
    pulseMat.color.setRGB(1.0, 0.4 + 0.6 * Math.sin(timeSeconds * 4), 0.2);

    // 4. Sparkles around Gate — slowly drift upward, burst at gate
    const sparkPosAttr = sparkleGeo.attributes.position;
    for (let i = 0; i < SPARKLE_COUNT; i++) {
      let py = sparkPosAttr.getY(i) + 0.005;
      if (py > GATE_POS[1] + 1.5) {
        // Reset to gate vicinity
        sparkPosAttr.setX(i, GATE_POS[0] + (Math.random() - 0.5) * 1.2);
        py = GATE_POS[1] - 0.8;
        sparkPosAttr.setZ(i, GATE_POS[2] + (Math.random() - 0.5) * 1.2);
      }
      sparkPosAttr.setY(i, py);
    }
    sparkPosAttr.needsUpdate = true;

    // 5. Compute Dynamic Coins
    const positions = [];

    coinConfigs.forEach((cfg, idx) => {
      const u = (timeSeconds / cfg.loopDuration + cfg.phaseOffset) % 1.0;
      const pt = evalLane(cfg.lane, u);

      // Subtle harmonic bobbing
      pt[1] += Math.sin(timeSeconds * cfg.bobSpeed + cfg.lane * 1.5) * cfg.bobAmp;

      // Pointer repulsion if nearby
      const dx = pt[0] - (basePosX + pointer.x * 8);
      const dy = pt[1] - (1.5 + pointer.y * 5);
      const d = Math.sqrt(dx * dx + dy * dy);
      if (d < 1.8) {
        pt[0] += (dx / (d + 0.1)) * (1.8 - d) * 0.15;
        pt[1] += (dy / (d + 0.1)) * (1.8 - d) * 0.15;
      }

      positions.push({
        id: idx,
        pos: pt,
        u,
        lane: cfg.lane,
        isStatic: false,
        radius: R
      });
    });

    // Add static coins
    STATIC_COIN_DEFS.forEach((sc, idx) => {
      positions.push({
        id: DYNAMIC_COUNT + idx,
        pos: [...sc.pos],
        rot: sc.rot,
        isStatic: true,
        radius: R,
        isRupee: sc.isRupee
      });
    });

    // 6. Multi-pass collision & avoidance solver
    for (let pass = 0; pass < 3; pass++) {
      for (let i = 0; i < positions.length; i++) {
        const c1 = positions[i];
        if (c1.isStatic) continue;

        // Card slab repulsion
        CARDS_DATA.forEach((card) => {
          const dx = c1.pos[0] - card.pos[0];
          const dy = c1.pos[1] - card.pos[1];
          const dz = c1.pos[2] - card.pos[2];
          const limitX = card.half[0] + R + 0.06;
          const limitY = card.half[1] + R + 0.06;
          const limitZ = card.half[2] + R + 0.06;

          if (Math.abs(dx) < limitX && Math.abs(dy) < limitY && Math.abs(dz) < limitZ) {
            const penX = limitX - Math.abs(dx);
            const penY = limitY - Math.abs(dy);
            const penZ = limitZ - Math.abs(dz);
            if (penZ <= penX && penZ <= penY) {
              c1.pos[2] = card.pos[2] + (dz >= 0 ? limitZ : -limitZ);
            } else if (penY <= penX) {
              c1.pos[1] = card.pos[1] + (dy >= 0 ? limitY : -limitY);
            } else {
              c1.pos[0] = card.pos[0] + (dx >= 0 ? limitX : -limitX);
            }
          }
        });

        // Floor clamping
        if (c1.pos[1] - R < FLOOR_Y + 0.05) {
          c1.pos[1] = FLOOR_Y + R + 0.05;
        }

        // Pairwise coin separation
        for (let j = i + 1; j < positions.length; j++) {
          const c2 = positions[j];
          const dx = c1.pos[0] - c2.pos[0];
          const dy = c1.pos[1] - c2.pos[1];
          const dz = c1.pos[2] - c2.pos[2];
          const dist = Math.sqrt(dx * dx + dy * dy + dz * dz);
          const minSafeDist = (c1.radius + c2.radius) + 0.06;

          if (dist < minSafeDist && dist > 1e-4) {
            const overlap = minSafeDist - dist;
            const nx = dx / dist;
            const ny = dy / dist;
            const nz = dz / dist;

            if (c2.isStatic) {
              c1.pos[0] += nx * overlap;
              c1.pos[1] += ny * overlap;
              c1.pos[2] += nz * overlap;
            } else {
              c1.pos[0] += nx * (overlap * 0.5);
              c1.pos[1] += ny * (overlap * 0.5);
              c1.pos[2] += nz * (overlap * 0.5);
              c2.pos[0] -= nx * (overlap * 0.5);
              c2.pos[1] -= ny * (overlap * 0.5);
              c2.pos[2] -= nz * (overlap * 0.5);
            }
          }
        }
      }
    }

    // 7. Apply positions, rotations, colors to meshes
    let liveMinGap = Infinity;

    positions.forEach((item, idx) => {
      const mesh = coinMeshes[idx];
      const shadow = shadowMeshes[idx];

      mesh.position.set(item.pos[0], item.pos[1], item.pos[2]);

      if (item.isStatic) {
        mesh.rotation.set(...item.rot);
        shadow.position.set(item.pos[0], FLOOR_Y + 0.003, item.pos[2]);
        shadow.scale.set(1.1, 1.1, 1.1);
        shadow.material.opacity = isDark ? 0.7 : 0.28;
      } else {
        // Dynamic orientation:
        // Before gate (u < 0.45): front face ($) visible, slow tumble
        // At gate (u between 0.45 and 0.55): smooth 180° flip
        // After gate (u > 0.55): back face (₹) visible!
        const flipProgress = Math.min(1, Math.max(0, (item.u - 0.45) / 0.1));
        const flipAngle = Math.PI * flipProgress;

        const tumbleX = Math.sin(timeSeconds * 0.8 + item.id) * 0.25;
        const tumbleY = (timeSeconds * 0.6 + item.id * 1.5) % (Math.PI * 2) + flipAngle;
        const tumbleZ = Math.cos(timeSeconds * 0.5 + item.id) * 0.15;

        mesh.rotation.set(tumbleX, tumbleY, tumbleZ);

        // Color transition: Silver/Gold -> Copper across gate
        const copperBlend = Math.min(1, Math.max(0, (item.u - 0.35) / 0.3));
        const instanceColor = colorSilver.clone().lerp(colorCopper, copperBlend);

        // Rim glow pulse right at gate
        if (Math.abs(item.u - 0.5) < 0.05) {
          instanceColor.addScalar(isDark ? 0.25 : 0.12);
        }

        // Contact shadow tracking
        const hAboveFloor = Math.max(0, item.pos[1] - FLOOR_Y);
        shadow.position.set(item.pos[0], FLOOR_Y + 0.003, item.pos[2]);
        const shadowScale = Math.max(0.6, 1.5 - hAboveFloor * 0.3);
        shadow.scale.set(shadowScale, shadowScale, shadowScale);
        shadow.material.opacity = Math.max(0.05, (isDark ? 0.6 : 0.28) - hAboveFloor * 0.12);
      }

      // Debug collision sphere
      if (debugGroup && debugGroup.children[idx]) {
        debugGroup.children[idx].position.copy(mesh.position);
      }
    });

    // Compute live minimum gap for debug HUD
    if (isDebugCollisions) {
      for (let i = 0; i < positions.length; i++) {
        for (let j = i + 1; j < positions.length; j++) {
          const dx = positions[i].pos[0] - positions[j].pos[0];
          const dy = positions[i].pos[1] - positions[j].pos[1];
          const dz = positions[i].pos[2] - positions[j].pos[2];
          const dist = Math.sqrt(dx * dx + dy * dy + dz * dz) - 2 * R;
          if (dist < liveMinGap) liveMinGap = dist;
        }
      }
      const hud = document.getElementById('collisionDebugHud');
      if (hud) {
        hud.textContent = `Coins: ${positions.length} | Min Gap: ${(liveMinGap / R).toFixed(3)}*R (${liveMinGap.toFixed(3)}u) | FPS: ${Math.round(fps)}`;
      }
    }
  }

  // ------------------------------------------------------------------------
  // Animation Loop & Performance Monitor
  // ------------------------------------------------------------------------
  function animate() {
    if (isPausedByUser || !isVisible || document.hidden) {
      rafId = requestAnimationFrame(animate);
      return;
    }

    const t = isTimeFrozen ? frozenTime : clock.getElapsedTime();

    // FPS & Quality governor
    frameCount++;
    const now = performance.now();
    if (now - lastTimeCheck >= 1000) {
      fps = (frameCount * 1000) / (now - lastTimeCheck);
      frameCount = 0;
      lastTimeCheck = now;

      // Adaptive quality governor: if FPS drops below 40, lower DPR
      if (fps < 40 && currentDprStep > 1.0) {
        currentDprStep = Math.max(1.0, currentDprStep - 0.25);
        renderer.setPixelRatio(currentDprStep);
        console.warn(`[CoinScene] Adaptive step-down: DPR reduced to ${currentDprStep}`);
      }
    }

    updateScene(t);
    renderer.render(scene, camera);

    if (!isTimeFrozen) {
      rafId = requestAnimationFrame(animate);
    }
  }

  // Kick off animation or render single still if reduced motion / frozen
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (prefersReduced || isTimeFrozen) {
    updateScene(frozenTime);
    renderer.render(scene, camera);
  } else {
    animate();
  }

  // ------------------------------------------------------------------------
  // Theme Crossfade (Smooth ~400ms transition without remounting)
  // ------------------------------------------------------------------------
  function updateTheme(newTheme) {
    const dark = newTheme !== 'light';
    const newBg = dark ? 0x0c0c0e : 0xF3F1EE;

    scene.fog.color.setHex(newBg);
    scene.fog.near = dark ? 8 : 18;
    scene.fog.far  = dark ? 26 : 38;
    floorMat.color.setHex(newBg);
    floorMat.roughness = dark ? 0.35 : 0.55;

    ambientLight.color.setHex(dark ? 0x222834 : 0xF5E8D0);
    ambientLight.intensity = dark ? 1.2 : 1.0;

    keyLight.intensity      = dark ? 2.8 : 1.8;
    orangeRimLight.intensity = dark ? 2.5 : 1.2;
    warmRimLight.intensity  = dark ? 0   : 0.85;
    fillLight.intensity     = dark ? 1.4 : 0.6;
    fillLight.color.setHex(dark ? 0x4D88FF : 0xE8C89A);

    renderer.toneMappingExposure = dark ? 1.25 : 0.95;

    // Build new studio environment
    if (currentEnvTexture) currentEnvTexture.dispose();
    currentEnvTexture = buildStudioEnvironment(THREE, pmremGenerator, newTheme);
    scene.environment = currentEnvTexture;

    // Refresh coin materials
    const p = LIGHT_COIN_PALETTES[lightCoinParam] || LIGHT_COIN_PALETTES['copper-gold'];
    const newField = dark ? new THREE.Color(1, 1, 1) : new THREE.Color(p.fieldBase);
    const newRim   = dark ? new THREE.Color(1, 1, 1) : new THREE.Color(p.rimBase);
    const newEnvInt = dark ? 1.6 : 1.7;
    const newRough  = dark ? 0.24 : 0.28;

    matFront.color.copy(newField);
    matFront.roughness = newRough;
    matFront.envMapIntensity = newEnvInt;
    matFront.needsUpdate = true;

    matBack.color.copy(newField);
    matBack.roughness = newRough;
    matBack.envMapIntensity = newEnvInt;
    matBack.needsUpdate = true;

    matEdge.color.copy(newRim);
    matEdge.roughness = dark ? 0.18 : 0.15;
    matEdge.envMapIntensity = dark ? 1.5 : 1.6;
    matEdge.needsUpdate = true;

    arcTubeMat.emissiveIntensity = dark ? 2.0 : 0.9;
    gateTorusMat.emissiveIntensity = dark ? 2.5 : 1.0;

    // Regenerate card canvases with new theme (for readability)
    cardMeshes.forEach(({ mesh }, i) => {
      const cData = CARDS_DATA[i];
      const newCanvas = createGlassCardCanvas(cData.title, cData.sub, cData.val, cData.change, newTheme);
      const newTex = new THREE.CanvasTexture(newCanvas);
      newTex.anisotropy = maxAnisotropy;
      if (mesh.material.map) mesh.material.map.dispose();
      mesh.material.map = newTex;
      mesh.material.opacity = dark ? 0.94 : 0.96;
      mesh.material.needsUpdate = true;
    });

    // Camera framing for new theme
    const newCamPosX  = dark ? 0 : 2.0;
    camera.position.set(newCamPosX, camera.position.y, camera.position.z);

    // Render immediate update if paused/frozen
    if (isTimeFrozen || prefersReduced) {
      updateScene(frozenTime);
      renderer.render(scene, camera);
    }
  }

  // Pause / Play toggle
  function togglePause() {
    isPausedByUser = !isPausedByUser;
    if (!isPausedByUser) {
      clock.start();
      animate();
    }
    return isPausedByUser;
  }

  // Cleanup
  function destroy() {
    cancelAnimationFrame(rafId);
    observer.disconnect();
    window.removeEventListener('mousemove', onPointerMove);
    window.removeEventListener('touchmove', onTouchMove);
    window.removeEventListener('scroll', onScroll);
    window.removeEventListener('resize', onResize);

    pmremGenerator.dispose();
    if (currentEnvTexture) currentEnvTexture.dispose();
    renderer.dispose();
    if (renderer.domElement.parentNode) {
      renderer.domElement.parentNode.removeChild(renderer.domElement);
    }
  }

  return { updateTheme, togglePause, destroy };
}
