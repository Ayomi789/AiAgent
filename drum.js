(() => {
    'use strict';

    const STEPS = 16;

    const DRUMS = [
        { id: 'kick',    name: 'Kick',     file: '01 - JavaScript Drum Kit_sounds_kick.wav',    key: 'f', color: '#ff5f56', soft: 'rgba(255, 95, 86, 0.35)'    },
        { id: 'snare',   name: 'Snare',    file: '01 - JavaScript Drum Kit_sounds_snare.wav',   key: 'h', color: '#ff7aa2', soft: 'rgba(255, 122, 162, 0.35)' },
        { id: 'clap',    name: 'Clap',     file: '01 - JavaScript Drum Kit_sounds_clap.wav',    key: 's', color: '#b388ff', soft: 'rgba(179, 136, 255, 0.35)' },
        { id: 'tom',     name: 'Tom',      file: '01 - JavaScript Drum Kit_sounds_tom (1).wav', key: 'j', color: '#69db7c', soft: 'rgba(105, 219, 124, 0.35)' },
        { id: 'hihat',   name: 'Hi-Hat',   file: '01 - JavaScript Drum Kit_sounds_hihat.wav',   key: 'd', color: '#4dd0e1', soft: 'rgba(77, 208, 225, 0.35)'   },
        { id: 'openhat', name: 'Open Hat', file: '01 - JavaScript Drum Kit_sounds_openhat.wav', key: 'g', color: '#3ddc97', soft: 'rgba(61, 220, 151, 0.35)'   },
        { id: 'boom',    name: 'Boom',     file: '01 - JavaScript Drum Kit_sounds_boom.wav',    key: 'a', color: '#ffb84d', soft: 'rgba(255, 184, 77, 0.35)'   },
        { id: 'tink',    name: 'Tink',     file: '01 - JavaScript Drum Kit_sounds_tink.wav',    key: 'k', color: '#74c0fc', soft: 'rgba(116, 192, 252, 0.35)'   },
    ];

    const PRESETS = {
        showcase: { kick: [0, 6, 10],                   snare: [4, 12],          hihat: [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], openhat: [14], clap: [4, 12], tom: [13], boom: [0], tink: [0, 2, 4, 6, 8, 10, 12, 14] },
        // Kanye West – Runaway hook as a drum cover: each step = one 8th of the
        // melody (E5 E5 E5 | D#5×4 | C#5×3 | A4 A4 | G#4 | E4 E4 | B4), pitched
        // onto the drums so the contour is audible (high → low).
        runaway: { bpm: 45, kick: [13, 14],             snare: [12],             hihat: [3, 4, 5, 6],                  openhat: [7, 8, 9],   clap: [10, 11], tom: [],   boom: [15], tink: [0, 1, 2] },
        rock:   { kick: [0, 8],                          snare: [4, 12],          hihat: [0, 2, 4, 6, 8, 10, 12, 14],  openhat: [],          clap: [],   tom: [14], boom: [], tink: [] },
        hiphop: { kick: [0, 7, 10],                      snare: [4, 12],          hihat: [0, 3, 6, 8, 11, 14],          openhat: [14],        clap: [],   tom: [],   boom: [0], tink: [] },
        funk:   { kick: [0, 6, 10],                      snare: [4, 12],          hihat: [0, 2, 4, 6, 8, 10, 11, 12, 14], openhat: [],          clap: [],   tom: [14], boom: [0], tink: [] },
        four:   { kick: [0, 4, 8, 12],                   snare: [],               hihat: [2, 6, 10, 14],                openhat: [],          clap: [4, 12], tom: [],   boom: [], tink: [] },
    };

    // ---- Elements ----
    const padsEl = document.getElementById('pads');
    const seqEl = document.getElementById('sequencer');
    const playBtn = document.getElementById('playBtn');
    const clearBtn = document.getElementById('clearBtn');
    const loader = document.getElementById('loader');
    const bpmInput = document.getElementById('bpm');
    const swingInput = document.getElementById('swing');
    const volInput = document.getElementById('volume');
    const bpmVal = document.getElementById('bpmVal');
    const swingVal = document.getElementById('swingVal');
    const volVal = document.getElementById('volVal');

    // ---- State ----
    const pattern = {};
    const pads = {};
    const stepCells = [];
    DRUMS.forEach((d) => { pattern[d.id] = Array(STEPS).fill(false); });

    let bpm = 100;
    let swing = 0;
    let vol = 0.8;
    let ctx = null;
    let masterGain = null;
    const buffers = {};
    const audioEls = {};
    let engine = 'webaudio';

    let isPlaying = false;
    let currentStep = 0;
    let nextNoteTime = 0;
    let schedTimer = null;
    let lastShown = -1;

    const sixteenth = () => (60 / bpm) / 4;

    // ---- Audio ----
    function getCtx() {
        if (!ctx) {
            const AC = window.AudioContext || window.webkitAudioContext;
            ctx = new AC();
            masterGain = ctx.createGain();
            masterGain.gain.value = vol;
            masterGain.connect(ctx.destination);
        }
        if (ctx.state === 'suspended') ctx.resume();
        return ctx;
    }

    async function loadSamples() {
        try {
            const c = getCtx();
            await Promise.all(DRUMS.map(async (d) => {
                const res = await fetch(encodeURI(d.file));
                if (!res.ok) throw new Error('HTTP ' + res.status);
                const buf = await res.arrayBuffer();
                buffers[d.id] = await c.decodeAudioData(buf);
            }));
            engine = 'webaudio';
        } catch (err) {
            // Fallback for file:// — play via cloned <audio> elements instead.
            engine = 'audio';
            DRUMS.forEach((d) => {
                const a = document.createElement('audio');
                a.preload = 'auto';
                a.src = encodeURI(d.file);
                audioEls[d.id] = a;
            });
        }
        loader.classList.add('hidden');
    }

    function playDrum(id, time = null) {
        const c = getCtx();
        const when = time == null ? c.currentTime : time;

        if (engine === 'webaudio' && buffers[id]) {
            const src = c.createBufferSource();
            src.buffer = buffers[id];
            src.connect(masterGain);
            src.start(when);
        } else if (engine === 'audio' && audioEls[id]) {
            const delay = Math.max(0, (when - c.currentTime) * 1000);
            setTimeout(() => {
                const el = audioEls[id].cloneNode();
                el.volume = vol;
                el.play().catch(() => {});
            }, delay);
        }

        const flashDelay = Math.max(0, (when - c.currentTime) * 1000);
        flashPad(id, flashDelay);
    }

    function flashPad(id, delay) {
        const el = pads[id];
        if (!el) return;
        setTimeout(() => {
            el.classList.add('hit');
            setTimeout(() => el.classList.remove('hit'), 140);
        }, delay);
    }

    // ---- UI build: pads ----
    DRUMS.forEach((d) => {
        const pad = document.createElement('button');
        pad.type = 'button';
        pad.className = 'pad';
        pad.dataset.drum = d.id;
        pad.style.setProperty('--accent', d.color);
        pad.style.setProperty('--accent-soft', d.soft);
        pad.setAttribute('aria-label', d.name + ' (key ' + d.key.toUpperCase() + ')');
        pad.innerHTML = '<span class="pad-name">' + d.name + '</span><kbd>' + d.key.toUpperCase() + '</kbd>';
        pad.addEventListener('pointerdown', (e) => {
            e.preventDefault();
            playDrum(d.id);
        });
        pad.addEventListener('pointerup', () => pad.blur());
        padsEl.appendChild(pad);
        pads[d.id] = pad;
    });

    // ---- UI build: sequencer ----
    DRUMS.forEach((d, di) => {
        const row = document.createElement('div');
        row.className = 'seq-row';
        row.style.setProperty('--accent', d.color);
        row.style.setProperty('--accent-soft', d.soft);

        const label = document.createElement('div');
        label.className = 'seq-label';
        label.textContent = d.name;
        row.appendChild(label);

        const cells = [];
        for (let s = 0; s < STEPS; s++) {
            const cell = document.createElement('button');
            cell.type = 'button';
            cell.className = 'step' + (s % 4 === 0 ? ' beat' : '');
            cell.dataset.step = s;
            cell.setAttribute('aria-label', d.name + ' step ' + (s + 1));
            cell.addEventListener('click', () => {
                pattern[d.id][s] = !pattern[d.id][s];
                cell.classList.toggle('on', pattern[d.id][s]);
            });
            row.appendChild(cell);
            cells.push(cell);
        }
        seqEl.appendChild(row);
        stepCells.push(cells);
    });

    // ---- Transport / sequencer ----
    function setStepHighlight(step) {
        if (step === lastShown) return;
        if (lastShown >= 0) {
            stepCells.forEach((cells) => cells[lastShown].classList.remove('current'));
        }
        lastShown = step;
        if (step >= 0) {
            stepCells.forEach((cells) => cells[step].classList.add('current'));
        }
    }

    function startSequencer() {
        const c = getCtx();
        isPlaying = true;
        playBtn.classList.add('playing');
        playBtn.textContent = '⏸ Stop';
        currentStep = 0;
        lastShown = -1;
        nextNoteTime = c.currentTime + 0.06;
        schedTimer = setInterval(scheduler, 25);
    }

    function stopSequencer() {
        isPlaying = false;
        clearInterval(schedTimer);
        schedTimer = null;
        playBtn.classList.remove('playing');
        playBtn.textContent = '▶ Play';
        setStepHighlight(-1);
    }

    function togglePlay() {
        isPlaying ? stopSequencer() : startSequencer();
    }

    function scheduler() {
        const c = getCtx();
        const lookahead = 0.12;
        while (nextNoteTime < c.currentTime + lookahead) {
            scheduleStep(currentStep, nextNoteTime);
            nextNoteTime += sixteenth();
            currentStep = (currentStep + 1) % STEPS;
        }
        setStepHighlight(currentStep);
    }

    function scheduleStep(step, time) {
        let t = time;
        if (swing > 0 && step % 2 === 1) {
            t += (swing / 100) * 0.5 * sixteenth();
        }
        DRUMS.forEach((d) => {
            if (pattern[d.id][step]) playDrum(d.id, t);
        });
    }

    // ---- Pattern editing ----
    function clearPattern() {
        DRUMS.forEach((d) => {
            pattern[d.id].fill(false);
        });
        stepCells.forEach((cells) => cells.forEach((c) => c.classList.remove('on')));
    }

    function applyPreset(name) {
        clearPattern();
        const p = PRESETS[name];
        DRUMS.forEach((d) => {
            (p[d.id] || []).forEach((s) => {
                pattern[d.id][s] = true;
                stepCells[DRUMS.indexOf(d)][s].classList.add('on');
            });
        });
        if (p.bpm) {
            bpm = p.bpm;
            bpmInput.value = bpm;
            bpmVal.textContent = bpm;
        }
    }

    // ---- Events ----
    playBtn.addEventListener('click', togglePlay);
    clearBtn.addEventListener('click', clearPattern);

    document.querySelectorAll('.preset').forEach((btn) => {
        btn.addEventListener('click', () => applyPreset(btn.dataset.preset));
    });

    bpmInput.addEventListener('input', () => {
        bpm = Number(bpmInput.value);
        bpmVal.textContent = bpm;
    });

    swingInput.addEventListener('input', () => {
        swing = Number(swingInput.value);
        swingVal.textContent = swing + '%';
    });

    volInput.addEventListener('input', () => {
        vol = Number(volInput.value) / 100;
        volVal.textContent = Math.round(vol * 100) + '%';
        if (ctx && masterGain) masterGain.gain.setTargetAtTime(vol, ctx.currentTime, 0.02);
    });

    document.addEventListener('keydown', (e) => {
        if (e.metaKey || e.ctrlKey || e.altKey) return;
        if (e.key === ' ') {
            if (!e.repeat) {
                e.preventDefault();
                togglePlay();
            }
            return;
        }
        if (e.repeat) return;
        const k = e.key.toLowerCase();
        const drum = DRUMS.find((d) => d.key === k);
        if (drum) playDrum(drum.id);
    });

    // ---- Init ----
    applyPreset('showcase');
    loadSamples();
})();
