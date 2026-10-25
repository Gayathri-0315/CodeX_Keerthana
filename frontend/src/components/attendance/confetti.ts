// A light confetti burst: ~24 particles on a canvas, under 900 ms. Loaded only when someone registers.
const COLORS = ["#0071e3", "#30d158", "#ff9f0a", "#ff375f", "#5ac8fa", "#bf5af2"];

export default function burst(origin: { x: number; y: number }) {
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const canvas = document.createElement("canvas");
  const dpr = Math.min(2, window.devicePixelRatio || 1);
  canvas.width = window.innerWidth * dpr;
  canvas.height = window.innerHeight * dpr;
  Object.assign(canvas.style, { position: "fixed", inset: "0", width: "100%", height: "100%", pointerEvents: "none", zIndex: "80" });
  document.body.appendChild(canvas);
  const ctx = canvas.getContext("2d")!;
  ctx.scale(dpr, dpr);

  const parts = Array.from({ length: 24 }, (_, i) => {
    const angle = -Math.PI / 2 + (Math.random() - 0.5) * Math.PI * 1.1;
    const speed = 7 + Math.random() * 6;
    return {
      x: origin.x, y: origin.y,
      vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
      size: 5 + Math.random() * 4, rot: Math.random() * Math.PI, vr: (Math.random() - 0.5) * 0.4,
      color: COLORS[i % COLORS.length],
    };
  });

  const start = performance.now();
  const DURATION = 850;
  const frame = (t: number) => {
    const k = (t - start) / DURATION;
    ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
    if (k >= 1) {
      canvas.remove();
      return;
    }
    ctx.globalAlpha = 1 - k * k;
    for (const p of parts) {
      p.vy += 0.35;
      p.vx *= 0.985;
      p.x += p.vx;
      p.y += p.vy;
      p.rot += p.vr;
      ctx.save();
      ctx.translate(p.x, p.y);
      ctx.rotate(p.rot);
      ctx.fillStyle = p.color;
      ctx.fillRect(-p.size / 2, -p.size / 3, p.size, (p.size * 2) / 3);
      ctx.restore();
    }
    requestAnimationFrame(frame);
  };
  requestAnimationFrame(frame);
}
