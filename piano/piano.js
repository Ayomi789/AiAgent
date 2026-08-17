(() => {
    'use strict';

    const BASE = 60; // C4
    const NOTE_NAMES = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B'];

    // C4..F5: 11 white + 7 black keys. `off` = semitones above C4, `key` = computer key.
    const KEYS = [
        { off: 0,  type: 'w', key: 'a' },
        { off: 1,  type: 'b', key: 'w' },
        { off: 2,  type: 'w', key: 's' },
        { off: 3,  type: 'b', key: 'e' },
        { off: 4,  type: 'w', key: 'd' },
        { off: 5,  type: 'w', key: 'f' },
        { off: 6,  type: 'b', key: 't' },
        { off: 7,  type: 'w', key: 'g' },
        { off: 8,  type: 'b', key: 'y' },
        { off: 9,  type: 'w', key: 'h' },
        { off: 10, type: 'b', key: 'u' },
        { off: 11, type: 'w', key: 'j' },
        { off: 12, type: 'w', key: 'k' },
        { off: 13, type: 'b', key: 'o' },
        { off: 14, type: 'w', key: 'l' },
        { off: 15, type: 'b', key: 'p' },
        { off: 16, type: 'w', key: ';' },
        { off: 17, type: 'w', key: "'" },
    ];

    const KEYMAP = {};
    KEYS.forEach((k) => { KEYMAP[k.key] = k.off; });

    const WHITE_W = 100 / KEYS.filter((k) => k.type === 'w').length;
    const BLACK_W = WHITE_W * 0.62;

    // ---- Elements ----
    const keysEl = document.getElementById('keys');
    const playBtn = document.getElementById('playBtn');
    const recBtn = document.getElementById('recBtn');
    const clearBtn = document.getElementById('clearBtn');
    const octDown = document.getElementById('octDown');
    const octUp = document.getElementById('octUp');
    const octVal = document.getElementById('octVal');
    const pedalBtn = document.getElementById('pedalBtn');
    const volInput = document.getElementById('volume');
    const volVal = document.getElementById('volVal');
    const statusEl = document.getElementById('status');

    // ---- State ----
    const keyEls = [];
    let octave = 0;
    let pedal = false;
    let vol = 0.8;

    const take = [];
    let takeLength = 8;
    let isRecording = false;
    let recStart = 0;

    let isPlaying = false;
    let playTimer = null;
    let nextAbs = 0;
    let nextIdx = 0;

    const voices = new Map(); // midi -> Set of live voices
    const pointerNotes = new Map(); // pointerId -> midi

    let ctx = null;
    let master = null;
    let reverbGain = null;

    const midiName = (m) => NOTE_NAMES[m % 12] + (Math.floor(m / 12) - 1);
    const midiFreq = (m) => 440 * Math.pow(2, (m - 69) / 12);

    // ---- Songs (transcribed loops) ----
    const NOTE_MIDI = { C: 0, 'C#': 1, D: 2, 'D#': 3, E: 4, F: 5, 'F#': 6, G: 7, 'G#': 8, A: 9, 'A#': 10, B: 11 };
    const midiFromName = (name) => {
        const letter = name.slice(0, name.length - 1);
        const oct = Number(name.slice(-1));
        return NOTE_MIDI[letter] + (oct + 1) * 12;
    };

    const SONGS = {
        // Kanye West – Runaway (intro hook): 2 bars of straight 8ths at ~90 BPM.
        runaway: (() => {
            const EIGHTH = 60 / 90 / 2;
            const melody = ['E5', 'E5', 'E5', 'D#5', 'D#5', 'D#5', 'D#5', 'C#5', 'C#5', 'C#5', 'A4', 'A4', 'G#4', 'E4', 'E4', 'B4'];
            return melody.map((n, i) => ({ midi: midiFromName(n), t: i * EIGHTH, dur: 0.3, vel: 0.85 }));
        })(),
    };

    // ---- Audio graph ----
    function ensureCtx() {
        if (!ctx) {
            const AC = window.AudioContext || window.webkitAudioContext;
            ctx = new AC();
            master = ctx.createGain();
            master.gain.value = vol;

            const convolver = ctx.createConvolver();
            convolver.buffer = makeImpulse(2.2, 2.4);
            reverbGain = ctx.createGain();
            reverbGain.gain.value = 0.3;
            reverbGain.connect(convolver);
            convolver.connect(master);

            master.connect(ctx.destination);
        }
        if (ctx.state === 'suspended') ctx.resume();
        return ctx;
    }

    function makeImpulse(seconds, decay) {
        const rate = ctx.sampleRate;
        const len = Math.floor(rate * seconds);
        const buf = ctx.createBuffer(2, len, rate);
        for (let ch = 0; ch < 2; ch++) {
            const data = buf.getChannelData(ch);
            for (let i = 0; i < len; i++) {
                data[i] = (Math.random() * 2 - 1) * Math.pow(1 - i / len, decay);
            }
        }
        return buf;
    }

    // ---- Voice ----
    function startVoice(midi, vel, t) {
        const c = ensureCtx();
        const f = midiFreq(midi);
        const g = c.createGain();
        g.gain.setValueAtTime(0.0001, t);
        g.gain.exponentialRampToValueAtTime(Math.max(0.0002, vel), t + 0.004);

        // Partial ladder — brighter partials decay faster (piano-like timbre).
        [[1, 1.0, 2.4], [2, 0.5, 1.7], [3, 0.25, 1.2], [4, 0.12, 0.8]].forEach(([mult, amp, dur]) => {
            const o = c.createOscillator();
            o.type = 'sine';
            o.frequency.value = f * mult;
            const pg = c.createGain();
            pg.gain.setValueAtTime(amp * vel, t + 0.004);
            pg.gain.exponentialRampToValueAtTime(0.0001, t + dur);
            o.connect(pg);
            pg.connect(g);
            o.start(t);
            o.stop(t + dur + 0.05);
        });

        // Warm body tone.
        const body = c.createOscillator();
        body.type = 'triangle';
        body.frequency.value = f;
        const bg = c.createGain();
        bg.gain.setValueAtTime(0.22 * vel, t + 0.004);
        bg.gain.exponentialRampToValueAtTime(0.0001, t + 1.5);
        body.connect(bg);
        bg.connect(g);
        body.start(t);
        body.stop(t + 1.6);

        g.connect(master);
        g.connect(reverbGain);
        return { midi, gain: g };
    }

    function releaseVoice(v, when = null) {
        const c = ensureCtx();
        const t = when == null ? c.currentTime : when;
        try {
            v.gain.gain.cancelScheduledValues(t);
            v.gain.gain.setTargetAtTime(0.0001, t, 0.06);
        } catch (e) { /* voice already gone */ }
        const set = voices.get(v.midi);
        if (set) set.delete(v);
    }

    function releaseAllVoices() {
        Array.from(voices.values()).forEach((set) => {
            Array.from(set).forEach((v) => releaseVoice(v));
        });
    }

    // ---- Live input ----
    function noteOn(midi, vel) {
        const c = ensureCtx();
        const set = voices.get(midi);
        if (set) Array.from(set).forEach((v) => releaseVoice(v));
        const v = startVoice(midi, vel, c.currentTime);
        if (!voices.has(midi)) voices.set(midi, new Set());
        voices.get(midi).add(v);
        if (isRecording) recordNoteOn(midi, vel);
        keyState(midi, 'down', true);
    }

    function noteOff(midi) {
        keyState(midi, 'down', false);
        if (pedal) {
            // sustain the sound until the pedal lifts
            if (isRecording) recordNoteOff(midi);
            return;
        }
        const set = voices.get(midi);
        if (set) Array.from(set).forEach((v) => releaseVoice(v));
        if (isRecording) recordNoteOff(midi);
    }

    function keyState(midi, cls, on) {
        const el = keyEls.find((e) => Number(e.dataset.midi) === midi);
        if (el) el.classList.toggle(cls, on);
    }

    function flashKeyAt(midi, t) {
        const delay = Math.max(0, (t - ensureCtx().currentTime) * 1000);
        setTimeout(() => {
            keyState(midi, 'flash', true);
            setTimeout(() => keyState(midi, 'flash', false), 130);
        }, delay);
    }

    // ---- Recording ----
    function updateTakeLength() {
        let end = 0;
        take.forEach((e) => { end = Math.max(end, e.t + e.dur); });
        takeLength = Math.max(8, end + 1.2);
        updateStatus();
    }

    function recordNoteOn(midi, vel) {
        take.push({ midi, t: Math.max(0, ensureCtx().currentTime - recStart), vel, dur: null });
        updateStatus();
    }

    function recordNoteOff(midi) {
        // Close the latest open event for this note; with the pedal down it stays
        // open until the pedal lifts or recording stops.
        for (let i = take.length - 1; i >= 0; i--) {
            const e = take[i];
            if (e.midi === midi && e.dur == null) {
                if (!pedal) e.dur = Math.max(0.06, ensureCtx().currentTime - recStart - e.t);
                break;
            }
        }
        updateTakeLength();
    }

    function closeOpenEvents(now) {
        take.forEach((e) => {
            if (e.dur == null) e.dur = Math.max(0.06, now - recStart - e.t);
        });
        updateTakeLength();
    }

    function startRecording() {
        const c = ensureCtx();
        stopPlayback();
        take.length = 0;
        isRecording = true;
        recStart = c.currentTime + 0.05;
        takeLength = 8;
        recBtn.classList.add('recording');
        updateStatus();
    }

    function stopRecording() {
        if (!isRecording) return;
        isRecording = false;
        recBtn.classList.remove('recording');
        closeOpenEvents(ensureCtx().currentTime);
    }

    function updateStatus() {
        statusEl.textContent = take.length + ' notes · ' + takeLength.toFixed(1) + ' s loop';
    }

    // ---- Playback ----
    function loadSong(name) {
        const song = SONGS[name];
        if (!song) return;
        stopPlayback();
        stopRecording();
        take.length = 0;
        song.forEach((e) => take.push({ midi: e.midi, t: e.t, dur: e.dur, vel: e.vel }));
        const last = song[song.length - 1];
        takeLength = last.t + last.dur + 0.8;
        startPlayback();
        const btn = document.querySelector('.song-btn[data-song="' + name + '"]');
        if (btn) btn.classList.add('playing');
        updateStatus();
    }

    function startPlayback() {
        if (take.length === 0) return;
        document.querySelectorAll('.song-btn').forEach((b) => b.classList.remove('playing'));
        const c = ensureCtx();
        isPlaying = true;
        playBtn.classList.add('playing');
        playBtn.textContent = '⏸ Stop';
        nextIdx = 0;
        nextAbs = c.currentTime + 0.08 + take[0].t;
        playTimer = setInterval(tick, 25);
    }

    function stopPlayback() {
        isPlaying = false;
        clearInterval(playTimer);
        playTimer = null;
        playBtn.classList.remove('playing');
        playBtn.textContent = '▶ Play';
    }

    function tick() {
        const c = ensureCtx();
        const horizon = c.currentTime + 0.12;
        while (nextAbs < horizon) {
            const e = take[nextIdx];
            const v = startVoice(e.midi, e.vel, nextAbs);
            v.gain.gain.setTargetAtTime(0.0001, nextAbs + e.dur, 0.06);
            flashKeyAt(e.midi, nextAbs);

            const curT = e.t;
            nextIdx = (nextIdx + 1) % take.length;
            const next = take[nextIdx];
            const off = next.t <= curT ? next.t + takeLength : next.t;
            nextAbs = nextAbs - curT + off;
        }
    }

    // ---- Transport buttons ----
    playBtn.addEventListener('click', () => {
        if (isRecording) stopRecording();
        isPlaying ? stopPlayback() : startPlayback();
    });

    recBtn.addEventListener('click', () => {
        isRecording ? stopRecording() : startRecording();
    });

    clearBtn.addEventListener('click', () => {
        stopPlayback();
        stopRecording();
        take.length = 0;
        takeLength = 8;
        releaseAllVoices();
        updateStatus();
    });

    document.querySelectorAll('.song-btn').forEach((btn) => {
        btn.addEventListener('click', () => loadSong(btn.dataset.song));
    });

    // ---- Pedal ----
    function togglePedal() {
        pedal = !pedal;
        pedalBtn.classList.toggle('active', pedal);
        if (!pedal) {
            releaseAllVoices();
            if (isRecording) closeOpenEvents(ensureCtx().currentTime);
        }
    }

    pedalBtn.addEventListener('click', togglePedal);

    // ---- Octave ----
    function updateKeys() {
        keyEls.forEach((el) => {
            const midi = BASE + octave * 12 + Number(el.dataset.off);
            el.dataset.midi = midi;
            el.querySelector('.note').textContent = midiName(midi);
        });
        octVal.textContent = midiName(BASE + octave * 12) + '–' + midiName(BASE + octave * 12 + 17);
    }

    function shiftOctave(delta) {
        octave = Math.max(-2, Math.min(2, octave + delta));
        updateKeys();
    }

    octDown.addEventListener('click', () => shiftOctave(-1));
    octUp.addEventListener('click', () => shiftOctave(1));

    // ---- Volume ----
    volInput.addEventListener('input', () => {
        vol = Number(volInput.value) / 100;
        volVal.textContent = Math.round(vol * 100) + '%';
        if (ctx && master) master.gain.setTargetAtTime(vol, ctx.currentTime, 0.02);
    });

    // ---- Keyboard input ----
    document.addEventListener('keydown', (e) => {
        if (e.metaKey || e.ctrlKey || e.altKey) return;
        const k = e.key.toLowerCase();
        if (e.repeat) return;

        if (k === ' ') {
            e.preventDefault();
            togglePedal();
            return;
        }
        if (k === 'r') {
            e.preventDefault();
            recBtn.click();
            return;
        }
        if (k === 'escape') {
            e.preventDefault();
            stopPlayback();
            stopRecording();
            return;
        }
        if (k === 'z') { shiftOctave(-1); return; }
        if (k === 'x') { shiftOctave(1); return; }

        const off = KEYMAP[k];
        if (off != null) noteOn(BASE + octave * 12 + off, 0.85);
    });

    document.addEventListener('keyup', (e) => {
        if (e.metaKey || e.ctrlKey || e.altKey) return;
        const off = KEYMAP[e.key.toLowerCase()];
        if (off != null) noteOff(BASE + octave * 12 + off);
    });

    // ---- Pointer input ----
    keysEl.addEventListener('pointerdown', (e) => {
        e.preventDefault();
        const el = e.target.closest('.key');
        if (!el) return;
        const midi = Number(el.dataset.midi);
        const rect = el.getBoundingClientRect();
        const y = (e.clientY - rect.top) / rect.height;
        const vel = Math.max(0.3, Math.min(1, 1 - y * 0.7));
        pointerNotes.set(e.pointerId, midi);
        noteOn(midi, vel);
    });

    function pointerRelease(e) {
        const midi = pointerNotes.get(e.pointerId);
        if (midi != null) {
            pointerNotes.delete(e.pointerId);
            noteOff(midi);
        }
    }

    document.addEventListener('pointerup', pointerRelease);
    document.addEventListener('pointercancel', pointerRelease);

    // ---- Build keyboard ----
    let whitesBefore = 0;
    KEYS.forEach((k) => {
        const el = document.createElement('button');
        el.type = 'button';
        el.className = 'key ' + (k.type === 'w' ? 'white' : 'black');
        el.dataset.off = k.off;
        if (k.type === 'w') {
            el.innerHTML = '<span class="note"></span><kbd>' + k.key.toUpperCase() + '</kbd>';
            keysEl.appendChild(el);
            whitesBefore++;
        } else {
            el.innerHTML = '<span class="note"></span>';
            const left = (whitesBefore - BLACK_W / 2 / WHITE_W) * WHITE_W;
            el.style.left = left + '%';
            el.style.width = BLACK_W + '%';
            keysEl.appendChild(el);
        }
        keyEls.push(el);
    });

    updateKeys();
})();
