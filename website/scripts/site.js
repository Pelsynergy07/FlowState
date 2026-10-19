// FlowState site behaviour. Plain JS, no build step.
(function () {
  "use strict";

  var root = document.documentElement;
  root.classList.add("js");

  // Which computer is this? Picks the primary download button and which
  // shortcuts the page shows ("win", "mac" or "other").
  var ua = navigator.userAgent || "";
  var isMobile = /Android|iPhone|iPad|iPod|Mobile/i.test(ua);
  var os = isMobile ? "other" : /Macintosh|Mac OS X/i.test(ua) ? "mac" : /Windows/i.test(ua) ? "win" : "other";
  root.dataset.os = os;
  Array.prototype.forEach.call(document.querySelectorAll(".dl-buttons"), function (group) {
    var buttons = Array.prototype.slice.call(group.querySelectorAll(".js-download"));
    var mine = buttons.filter(function (b) { return b.dataset.os === os; })[0];
    if (!mine) return;
    group.insertBefore(mine, group.firstChild);
    buttons.forEach(function (b) { if (b !== mine) b.classList.add("is-secondary"); });
  });
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  function storageGet(key) {
    try { return window.sessionStorage.getItem(key); } catch (e) { return null; }
  }
  function storageSet(key, value) {
    try { window.sessionStorage.setItem(key, value); } catch (e) { /* private mode */ }
  }

  // Light by default; the nav toggle switches to dark and remembers it.
  var toggle = document.getElementById("theme-toggle");
  function syncToggle() {
    var dark = root.dataset.theme === "dark";
    toggle.setAttribute("aria-label", dark ? "Switch to light mode" : "Switch to dark mode");
    toggle.firstElementChild.className = "ph " + (dark ? "ph-sun" : "ph-moon");
  }
  if (toggle) {
    syncToggle();
    toggle.addEventListener("click", function () {
      var dark = root.dataset.theme !== "dark";
      function apply() {
        if (dark) root.dataset.theme = "dark"; else delete root.dataset.theme;
        try { window.localStorage.setItem("flowstate-theme", dark ? "dark" : "light"); } catch (e) { /* private mode */ }
        syncToggle();
      }
      if (!document.startViewTransition || reduceMotion) { apply(); return; }

      // The new theme grows as a circle out of the toggle until it covers
      // the farthest corner of the screen.
      var r = toggle.getBoundingClientRect();
      var x = r.left + r.width / 2;
      var y = r.top + r.height / 2;
      var radius = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y));
      document.startViewTransition(apply).ready.then(function () {
        root.animate(
          { clipPath: ["circle(0px at " + x + "px " + y + "px)", "circle(" + radius + "px at " + x + "px " + y + "px)"] },
          { duration: 700, easing: "cubic-bezier(.65, 0, .35, 1)", pseudoElement: "::view-transition-new(root)" }
        );
      }).catch(function () { /* skipped (e.g. tab hidden); the theme is already applied */ });
    });
  }

  // Nav gets a hairline once the hero has scrolled away.
  var nav = document.querySelector(".nav");
  var heroTop = document.querySelector(".hero");
  if (nav && heroTop && "IntersectionObserver" in window) {
    new IntersectionObserver(function (entries) {
      nav.classList.toggle("is-scrolled", !entries[0].isIntersecting);
    }, { rootMargin: "-80px 0px 0px 0px" }).observe(heroTop.querySelector("h1"));
  }

  // Hero demo. Outputs are exactly what FlowState's formatter produces for
  // these words (checked against src/flowstate/text/pipeline.py).
  var examples = [
    {
      said: "hey priya hope you're doing well can we move tomorrow's design review to thursday thanks arjun",
      out: "Hey Priya,\n\nHope you're doing well. Can we move tomorrow's design review to Thursday?\n\nThanks,\nArjun"
    },
    {
      said: "before friday i need to finish three things first the onboarding flow second the pricing page third the empty states",
      out: "Before Friday I need to finish three things.\n\n1. The onboarding flow.\n2. The pricing page.\n3. The empty states."
    },
    {
      said: "can you make a list book the flights renew my passport and pay the electricity bill",
      out: "Can you make a list?\n\n- Book the flights\n- Renew my passport\n- Pay the electricity bill"
    },
    {
      said: "the build took um like ten minutes and i'm trying to um trying to figure out why",
      out: "The build took ten minutes, and I'm trying to figure out why."
    }
  ];

  var demo = document.querySelector(".demo");
  if (demo) {
    var tabs = Array.prototype.slice.call(demo.querySelectorAll("[role=tab]"));
    var saidEl = demo.querySelector(".said-text");
    var outEl = demo.querySelector(".out-text");
    var hud = demo.querySelector(".demo-hud");
    var timers = [];
    var current = 0;
    var visible = true;

    function clearTimers() {
      timers.forEach(clearTimeout);
      timers = [];
    }
    function later(fn, ms) { timers.push(setTimeout(fn, ms)); }

    function setHud(state) {
      hud.src = state === "processing" ? "assets/img/hud-processing.png" : "assets/img/hud-recording.png";
      hud.alt = state === "processing" ? "FlowState's recording bar, processing" : "FlowState's recording bar, listening";
    }

    function select(index) {
      current = index;
      tabs.forEach(function (tab, i) {
        tab.setAttribute("aria-selected", String(i === index));
        tab.tabIndex = i === index ? 0 : -1;
      });
    }

    function play(index) {
      clearTimers();
      select(index);
      var example = examples[index];
      var words = example.said.split(" ");
      saidEl.innerHTML = "";
      saidEl.setAttribute("aria-label", example.said);
      words.forEach(function (word, i) {
        var span = document.createElement("span");
        span.className = "word";
        span.textContent = word + (i < words.length - 1 ? " " : "");
        saidEl.appendChild(span);
      });
      outEl.textContent = example.out;

      if (reduceMotion) {
        Array.prototype.forEach.call(saidEl.children, function (s) { s.classList.add("is-on"); });
        setHud("processing");
        return;
      }

      setHud("recording");
      outEl.classList.add("is-hidden");
      var step = 140;
      Array.prototype.forEach.call(saidEl.children, function (span, i) {
        later(function () { span.classList.add("is-on"); }, 300 + i * step);
      });
      var spoken = 300 + words.length * step;
      later(function () { setHud("processing"); }, spoken + 250);
      later(function () {
        outEl.classList.remove("is-hidden");
        setHud("recording");
      }, spoken + 1100);
      later(function () {
        if (visible) play((current + 1) % examples.length);
      }, spoken + 6200);
    }

    tabs.forEach(function (tab, i) {
      tab.addEventListener("click", function () { play(i); });
      tab.addEventListener("keydown", function (e) {
        var next = null;
        if (e.key === "ArrowRight") next = (i + 1) % tabs.length;
        if (e.key === "ArrowLeft") next = (i - 1 + tabs.length) % tabs.length;
        if (next !== null) { e.preventDefault(); tabs[next].focus(); play(next); }
      });
    });

    // Pause the loop while the demo is off screen.
    if ("IntersectionObserver" in window && !reduceMotion) {
      new IntersectionObserver(function (entries) {
        var was = visible;
        visible = entries[0].isIntersecting;
        if (visible && !was) play(current);
        if (!visible) clearTimers();
      }).observe(demo);
    }
    play(0);
  }

  // Screenshot demo: drag a box, get the text FlowState pastes. The
  // reference block uses the app's own format (app.py _build_capture_references).
  var stage = document.getElementById("capture-stage");
  if (stage) {
    var box = document.getElementById("capture-box");
    var out = document.getElementById("capture-out");
    var pay = stage.querySelector(".mock-pay");
    var start = null;
    var count = 0;

    function rectFrom(a, b) {
      return { left: Math.min(a.x, b.x), top: Math.min(a.y, b.y), width: Math.abs(a.x - b.x), height: Math.abs(a.y - b.y) };
    }
    function local(e) {
      var r = stage.getBoundingClientRect();
      return { x: Math.max(0, Math.min(r.width, e.clientX - r.left)), y: Math.max(0, Math.min(r.height, e.clientY - r.top)) };
    }
    function draw(r) {
      box.hidden = false;
      box.style.left = r.left + "px";
      box.style.top = r.top + "px";
      box.style.width = r.width + "px";
      box.style.height = r.height + "px";
    }
    function coversPay(r) {
      var s = stage.getBoundingClientRect();
      var p = pay.getBoundingClientRect();
      var px = p.left - s.left, py = p.top - s.top;
      var overlapX = Math.max(0, Math.min(r.left + r.width, px + p.width) - Math.max(r.left, px));
      var overlapY = Math.max(0, Math.min(r.top + r.height, py + p.height) - Math.max(r.top, py));
      return overlapX * overlapY > 0.5 * p.width * p.height;
    }
    function result(onPay) {
      count += 1;
      var said = onPay ? "This button is crooked, can you fix it?" : "Can you check this part of the page?";
      var nearby = onPay ? "This button is crooked" : "Can you check this part of the page";
      var pre = document.createElement("pre");
      pre.textContent = said + "\n\n[Screenshots captured during this recording:]\n1. capture_" + count +
        ".png at 0:02 -- said around then: \"" + nearby + "\"";
      var thumb = document.createElement("span");
      thumb.className = "capture-thumb";
      thumb.textContent = "+ the screenshot itself, pasted after the text";
      out.innerHTML = '<span class="demo-label">FlowState pastes</span>';
      out.appendChild(pre);
      out.appendChild(thumb);
    }

    stage.addEventListener("pointerdown", function (e) {
      if (e.button !== 0) return;
      start = local(e);
      stage.setPointerCapture(e.pointerId);
      draw({ left: start.x, top: start.y, width: 0, height: 0 });
    });
    stage.addEventListener("pointermove", function (e) {
      if (start) draw(rectFrom(start, local(e)));
    });
    function finish(e) {
      if (!start) return;
      var r = rectFrom(start, local(e));
      start = null;
      if (r.width < 14 || r.height < 14) { box.hidden = true; return; }
      result(coversPay(r));
    }
    stage.addEventListener("pointerup", finish);
    stage.addEventListener("pointercancel", function () { start = null; box.hidden = true; });

    var showBtn = document.getElementById("capture-demo-btn");
    if (showBtn) {
      showBtn.addEventListener("click", function () {
        var s = stage.getBoundingClientRect();
        var p = pay.getBoundingClientRect();
        draw({ left: p.left - s.left - 12, top: p.top - s.top - 12, width: p.width + 24, height: p.height + 24 });
        result(true);
      });
    }
  }

  // Install steps: the screenshot on the right follows the step in view.
  var steps = Array.prototype.slice.call(document.querySelectorAll(".install-steps li"));
  var shots = Array.prototype.slice.call(document.querySelectorAll(".install-shots .shot"));
  function activate(index) {
    steps.forEach(function (s) { s.classList.toggle("is-active", s.dataset.shot === index); });
    shots.forEach(function (s) { s.classList.toggle("is-active", s.dataset.shot === index); });
  }
  if (steps.length && "IntersectionObserver" in window) {
    var stepObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) activate(entry.target.dataset.shot);
      });
    }, { rootMargin: "-45% 0px -50% 0px" });
    steps.forEach(function (s) { stepObserver.observe(s); });
    activate("0");
  }

  // Reveal sections as they arrive.
  if ("IntersectionObserver" in window && !reduceMotion) {
    var revealTargets = document.querySelectorAll(".how .wrap > *, .timeline li, .point-grid > *, .privacy .wrap > *, .install-steps, .faq-grid > *, .download-inner > *");
    var revealObserver = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-in");
          revealObserver.unobserve(entry.target);
        }
      });
    }, { rootMargin: "0px 0px -8% 0px" });
    Array.prototype.forEach.call(revealTargets, function (el, i) {
      el.classList.add("reveal");
      el.style.transitionDelay = (i % 3) * 70 + "ms";
      revealObserver.observe(el);
    });
  }

  // Latest release version and installer size from GitHub.
  function showRelease(info) {
    if (!info || !info.tag) return;
    var version = info.tag.replace(/^v/, "").replace(/-beta$/, " beta");
    var size = info.bytes ? (info.bytes / 1073741824).toFixed(1) + " GB" : null;
    if (info.macBytes) {
      Array.prototype.forEach.call(document.querySelectorAll(".js-size-mac"), function (el) {
        el.textContent = (info.macBytes / 1073741824).toFixed(1) + " GB";
      });
    }
    Array.prototype.forEach.call(document.querySelectorAll(".js-version"), function (el) { el.textContent = "Version " + version; });
    if (size) {
      Array.prototype.forEach.call(document.querySelectorAll(".js-size"), function (el) { el.textContent = size; });
      Array.prototype.forEach.call(document.querySelectorAll(".js-size-plain"), function (el) { el.textContent = size + " installer"; });
    }
  }
  var cached = storageGet("flowstate-release-v2");
  if (cached) {
    try { showRelease(JSON.parse(cached)); } catch (e) { /* ignore */ }
  } else if (window.fetch) {
    fetch("https://api.github.com/repos/Pelsynergy07/FlowState/releases/latest")
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) return;
        function sizeOf(name) {
          var asset = (data.assets || []).filter(function (a) { return a.name === name; })[0];
          return asset ? asset.size : 0;
        }
        var info = { tag: data.tag_name, bytes: sizeOf("FlowStateSetup.exe"), macBytes: sizeOf("FlowState-macOS.dmg") };
        storageSet("flowstate-release-v2", JSON.stringify(info));
        showRelease(info);
      })
      .catch(function () { /* keep the static fallback text */ });
  }

  // Phones and other systems can't run FlowState; say so next to the final button.
  var note = document.getElementById("platform-note");
  if (note) {
    if (os === "other") {
      note.hidden = false;
      note.textContent = isMobile
        ? "FlowState runs on Windows PCs and Macs. Open this page on your computer to install it."
        : "FlowState runs on Windows 10 and 11, and on Macs with Apple silicon. It isn't available for this system yet.";
      if (isMobile && navigator.clipboard) {
        var copy = document.createElement("button");
        copy.type = "button";
        copy.className = "btn btn-quiet btn-sm";
        copy.style.marginLeft = "10px";
        copy.textContent = "Copy link";
        copy.addEventListener("click", function () {
          navigator.clipboard.writeText("https://runflowstate.vercel.app/").then(function () {
            copy.textContent = "Link copied";
          }, function () {
            copy.textContent = "Couldn't copy";
          });
        });
        note.appendChild(copy);
      }
    }
  }
})();
