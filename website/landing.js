/* Local illustration only. No requests, analytics, uploads or application state. */
(() => {
  "use strict";
  const rows = [...document.querySelectorAll("[data-cue]")];
  const blocks = [...document.querySelectorAll("[data-block]")];
  const clock = document.getElementById("demo-clock");
  const caption = document.getElementById("demo-text");
  const playhead = document.getElementById("playhead");
  const toggle = document.getElementById("demo-toggle");
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  if (!rows.length || !toggle) return;
  let time = reduced.matches ? Number(rows[0].dataset.start) + 0.05 : 62.5;
  let paused = reduced.matches;
  let timer;
  function render() {
    const active = rows.findIndex(row => time >= Number(row.dataset.start) && time <= Number(row.dataset.end));
    const upcoming = rows.find(row => Number(row.dataset.start) > time) || rows[0];
    caption.textContent = (rows[active] || upcoming).querySelector("span").textContent;
    clock.textContent = `${String(Math.floor(time / 60)).padStart(2, "0")}:${String(Math.floor(time % 60)).padStart(2, "0")}`;
    playhead.style.left = `${(time - 60) * 4}%`;
    rows.forEach((row, index) => { row.classList.toggle("is-active", index === active); row.setAttribute("aria-pressed", String(index === active)); });
    blocks.forEach((block, index) => block.classList.toggle("is-active", index === active));
    toggle.textContent = paused ? "Play" : "Pause";
    toggle.setAttribute("aria-label", `${paused ? "Play" : "Pause"} illustration`);
  }
  function schedule() {
    clearInterval(timer);
    if (!paused && !document.hidden) timer = setInterval(() => { time = 60 + (time - 60 + 0.1) % 25; render(); }, 100);
  }
  rows.forEach(row => row.addEventListener("click", () => { time = Number(row.dataset.start) + 0.05; render(); }));
  toggle.addEventListener("click", () => { paused = !paused; schedule(); render(); });
  reduced.addEventListener("change", event => { paused = event.matches; if (paused) time = Number(rows[0].dataset.start) + 0.05; schedule(); render(); });
  document.addEventListener("visibilitychange", schedule);
  window.addEventListener("pagehide", () => clearInterval(timer));
  const header = document.querySelector(".landing-header");
  if (header && "ResizeObserver" in window) new ResizeObserver(() => document.documentElement.style.setProperty("--header-offset", `${header.getBoundingClientRect().height + 16}px`)).observe(header);
  render(); schedule();
})();
