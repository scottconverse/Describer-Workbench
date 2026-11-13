/* Landing page helpers. Runs only in the browser; sends no requests and stores nothing. */
(() => {
  "use strict";
  // Put the visitor's platform first in the download panel. Every download stays visible.
  const list = document.querySelector(".platform-downloads");
  const guess = document.getElementById("platform-guess");
  const ua = navigator.userAgent || "";
  const hint = ((navigator.userAgentData && navigator.userAgentData.platform) || navigator.platform || "").toLowerCase();
  const mobile = /android|iphone|ipad|ipod/i.test(ua);
  let key = null, label = "";
  if (!mobile) {
    if (hint.includes("win") || /windows/i.test(ua)) { key = "windows"; label = "Windows"; }
    else if (hint.includes("mac") || /macintosh/i.test(ua)) { key = "macos-arm64"; label = "a Mac"; }
    else if (hint.includes("linux") || /linux|x11/i.test(ua)) { key = "linux"; label = "Linux"; }
  }
  const match = key && list && list.querySelector(`[data-platform="${key}"]`);
  if (match) {
    match.classList.add("is-yours");
    list.prepend(match);
    if (guess) { guess.textContent = `You seem to use ${label}`; guess.hidden = false; }
  }
  // Keep anchor jumps clear of the sticky header.
  const header = document.querySelector(".landing-header");
  if (header && "ResizeObserver" in window) new ResizeObserver(() => document.documentElement.style.setProperty("--header-offset", `${header.getBoundingClientRect().height + 16}px`)).observe(header);
})();
