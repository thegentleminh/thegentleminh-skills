/* video-giai-thich runtime (MIT). Needs gsap and window.VGT (vgt-timing.js, written by `vgt.py sync`).
   Scene code calls vgtStart(tl => { ... }) and times things with:
     T("s4", 1.2)      1.2 s after scene s4 starts
     W("s4", "dội")    the moment the voice says "dội" in scene s4 (W("s6", "không", 2) = 2nd time) */
(function () {
  const V = window.VGT || { duration: 10, beats: {}, cues: [], words: [] };
  const norm = (s) => s.normalize("NFC").toLowerCase().replace(/[^\p{L}\p{N}]/gu, "");
  window.T = (beat, off = 0) => {
    if (!V.beats[beat]) throw new Error(`T: no scene "${beat}" in the script`);
    return V.beats[beat].start + off;
  };
  window.W = (beat, word, n = 1, off = 0) => {
    const k = norm(word);
    let c = 0;
    for (const w of V.words) if (w.beat === beat && norm(w.say) === k && ++c === n) return w.s + off;
    throw new Error(`W: "${word}" (#${n}) is not spoken in scene "${beat}"`);
  };
  window.Wend = (beat, word, n = 1) => {
    const k = norm(word);
    let c = 0;
    for (const w of V.words) if (w.beat === beat && norm(w.say) === k && ++c === n) return w.e;
    throw new Error(`Wend: "${word}" (#${n}) is not spoken in scene "${beat}"`);
  };

  const SAY_MAX_H = 350; // the sentence band: top of frame down to the picture
  function fit(node) {
    let size = parseFloat(getComputedStyle(node).fontSize);
    while (node.offsetHeight > SAY_MAX_H && size > 40) { size *= 0.95; node.style.fontSize = size.toFixed(1) + "px"; }
  }

  // on-screen sentences = the narration; each word appears as it is spoken
  function cues(tl, reveal) {
    V.cues.forEach((cue, ci) => {
      const sec = document.getElementById(cue.beat);
      const div = document.createElement("div");
      div.className = "say";
      div.id = `${cue.beat}-say${ci}`;
      // a highlighted phrase ("sóng dài") is one group: it never breaks across two lines and
      // carries one highlight box (looks with --hl-bg), which appears with the phrase's first word
      let group = null;
      const firstOf = new Map(); // word index -> group it opens
      cue.tokens.forEach((t, i) => {
        if (!t.hl) group = null;
        if (i) (group || div).appendChild(document.createTextNode(" "));
        if (t.hl && !group) {
          group = document.createElement("span");
          group.className = "hlg";
          div.appendChild(group);
          firstOf.set(i, group);
        }
        const s = document.createElement("span");
        s.className = "w" + (t.hl ? " hl" : "");
        s.textContent = t.show;
        (group || div).appendChild(s);
      });
      sec.appendChild(div);
      fit(div);
      const spans = div.querySelectorAll(".w");
      const groups = div.querySelectorAll(".hlg");
      const wordIn = (i) => (reveal === "sentence" ? cue.start + i * 0.025 : Math.max(cue.start, cue.tokens[i].s - 0.06));
      cue.tokens.forEach((t, i) => {
        tl.fromTo(spans[i], { y: 36, opacity: 0 }, { y: 0, opacity: 1, duration: 0.3, ease: "power3.out" }, wordIn(i));
        if (firstOf.has(i)) tl.fromTo(firstOf.get(i), { opacity: 0 }, { opacity: 1, duration: 0.2, ease: "none" }, wordIn(i));
      });
      if (cue.out) {
        tl.to(spans, { y: -26, opacity: 0, duration: 0.25, ease: "power2.in", stagger: 0.012 }, cue.end - 0.28);
        if (groups.length) tl.to(groups, { opacity: 0, duration: 0.25, ease: "power2.in" }, cue.end - 0.28);
      }
    });
  }

  // each scene's picture fades out just before the next scene
  function sceneFades(tl) {
    const ids = Object.keys(V.beats);
    ids.slice(0, -1).forEach((id) => {
      const sec = document.getElementById(id);
      if (!sec) return;
      const els = sec.querySelectorAll(":scope > .art, :scope > .label, :scope > .fade");
      if (els.length) tl.to(els, { opacity: 0, duration: 0.3, ease: "power1.in" }, V.beats[id].end - 0.4);
    });
  }

  function chalkFilter(root) {
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg");
    svg.setAttribute("width", "0"); svg.setAttribute("height", "0"); svg.style.position = "absolute";
    svg.innerHTML = `<filter id="chalk" x="-5%" y="-5%" width="110%" height="110%">
      <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" seed="4" result="n"/>
      <feDisplacementMap in="SourceGraphic" in2="n" scale="5" xChannelSelector="R" yChannelSelector="G" result="d"/>
      <feColorMatrix in="n" type="matrix" values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 -2.2 1.95" result="m"/>
      <feComposite in="d" in2="m" operator="in"/></filter>`;
    root.prepend(svg);
  }

  // vgtStart((tl) => { ...scenes... }, (tl) => { window.__timelines["main"] = tl; });
  window.vgtStart = function (scenes, register) {
    const vars = (window.__hyperframes && window.__hyperframes.getVariables && window.__hyperframes.getVariables()) || {};
    const root = document.getElementById("root");
    root.dataset.look = vars.look || root.dataset.look || "in-riso";
    chalkFilter(root);
    if (vars.handle) { // channel name, small, above the sentence band (inside every app's safe area)
      const h = document.createElement("div");
      h.id = "vgt-handle";
      h.textContent = vars.handle;
      root.appendChild(h);
    }
    const cs = getComputedStyle(root), v = (k) => cs.getPropertyValue(k).trim();
    return Promise.all([
      document.fonts.load(`${v("--say-weight")} 80px ${v("--say-font")}`, "Ằ ỡ"),
      document.fonts.load(`${v("--label-weight")} 40px ${v("--label-font")}`, "Ằ ỡ"),
    ]).then(() => document.fonts.ready).then(() => {
      const tl = gsap.timeline({ paused: true });
      cues(tl, vars.reveal || "word");
      scenes(tl);
      sceneFades(tl);
      // hand the timeline to the page's register callback. Never return it from a promise:
      // a GSAP timeline is "thenable", so the promise would wait for the (paused) timeline to finish.
      register(tl);
    }).catch((e) => {
      // a broken scene would otherwise leave every frame frozen at the start, with no message
      console.error("video-giai-thich: scene code failed: " + (e && e.stack ? e.stack : e));
      throw e;
    });
  };
})();
