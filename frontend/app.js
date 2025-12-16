// frontend/app.js

let audioCtx = null;
let nextPlayTime = 0;

let textSocket = null;
let audioSocket = null;

const statusLabel = document.getElementById("status-label");
const transcriptBox = document.getElementById("transcript-box");
const languageSelect = document.getElementById("language-select");
const startBtn = document.getElementById("start-btn");

const BACKEND_HOST = "94.57.27.161:8000"; // ← YOUR IP
const wsScheme = location.protocol === "https:" ? "wss" : "ws";
//const base = `${wsScheme}://${BACKEND_HOST}`;
const base = `${wsScheme}://${location.host}`;

// ----------------------------------
// Append text to transcript
// ----------------------------------
function appendSegment(source, translated) {
  const div = document.createElement("div");
  div.className = "transcript-segment";
  div.innerHTML = `<strong>${translated}</strong><br/><span style="color:#2D4D1E">${source}</span>`;
  transcriptBox.appendChild(div);
  transcriptBox.scrollTop = transcriptBox.scrollHeight;
}

// ----------------------------------
// Play PCM chunk
// ----------------------------------
function playPcm16Chunk(arrayBuffer) {
  if (!audioCtx) return;

  const int16 = new Int16Array(arrayBuffer);
  const float32 = new Float32Array(int16.length);

  for (let i = 0; i < int16.length; i++) {
    float32[i] = int16[i] / 32768.0;
  }

  const sampleRate = 16000;
  const audioBuffer = audioCtx.createBuffer(1, float32.length, sampleRate);
  audioBuffer.getChannelData(0).set(float32);

  const source = audioCtx.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(audioCtx.destination);

  const now = audioCtx.currentTime;
  if (nextPlayTime < now) nextPlayTime = now + 0.05;

  source.start(nextPlayTime);
  nextPlayTime += audioBuffer.duration;
}

// ----------------------------------
// CONNECT SOCKETS FOR A LANGUAGE
// ----------------------------------
function connectSockets(lang) {
    // ðŸ”¥ 1. ALWAYS close previous WebSockets before opening new ones
  if (textSocket && textSocket.readyState !== WebSocket.CLOSED) {
    try { textSocket.close(); } catch (_) {}
    textSocket = null;
  }

  if (audioSocket && audioSocket.readyState !== WebSocket.CLOSED) {
    try { audioSocket.close(); } catch (_) {}
    audioSocket = null;
  }

  // ðŸ”¥ 2. Reset audio scheduling so new language does not overlap with old one
  nextPlayTime = 0;

  // const wsScheme = location.protocol === "https:" ? "wss" : "ws";
  // const base = `${wsScheme}://${location.host}`;

  // TEXT SOCKET --------------------------
  const textUrl = `${base}/ws/text/${lang}`;
  textSocket = new WebSocket(textUrl);

  textSocket.onopen = () => {
    statusLabel.textContent = `Connected (text: ${lang})`;
  };

  textSocket.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      appendSegment(data.source, data.segment);
    } catch (e) {
      console.error(e);
    }
  };

  textSocket.onclose = () => console.log("Text WS closed");
  textSocket.onerror = (err) => console.log("Text WS error", err);

  // AUDIO SOCKET -------------------------
  const audioUrl = `${base}/ws/audio/${lang}`;
  audioSocket = new WebSocket(audioUrl);
  audioSocket.binaryType = "arraybuffer";

  audioSocket.onopen = () => {
    statusLabel.textContent = `Connected (text+audio: ${lang})`;
  };

  audioSocket.onmessage = (event) => {
    if (event.data instanceof ArrayBuffer) playPcm16Chunk(event.data);
    else event.data.arrayBuffer().then(playPcm16Chunk);
  };

  audioSocket.onclose = () => console.log("Audio WS closed");
  audioSocket.onerror = (err) => console.log("Audio WS error", err);
}

// ----------------------------------
// START BUTTON â€” RUNS ONLY ONCE
// ----------------------------------
startBtn.addEventListener("click", async () => {
  const lang = languageSelect.value;

  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
  }
  if (audioCtx.state === "suspended") await audioCtx.resume();

  startBtn.disabled = true;
  statusLabel.textContent = "Connecting...";

  connectSockets(lang);
});

// ----------------------------------
// AUTO LANGUAGE SWITCHING (THE FIX)
// ----------------------------------
languageSelect.addEventListener("change", async () => {
  console.log("ðŸ“Š BEFORE switch - Segments:", transcriptBox.children.length);
  console.log("ðŸ“Š BEFORE switch - HTML length:", transcriptBox.innerHTML.length);
  const lang = languageSelect.value;

  console.log("Switching language to:", lang);

  // Always clear transcript when switching
  // transcriptBox.innerHTML = "";


  // Close previous sockets immediately
  try { if (textSocket) textSocket.close(); } catch {}
  try { if (audioSocket) audioSocket.close(); } catch {}

  textSocket = null;
  audioSocket = null;
  nextPlayTime = 0;

  // Ensure audio context ready
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
  }
  if (audioCtx.state === "suspended") await audioCtx.resume();

  statusLabel.textContent = `Switching to ${lang}...`;

  // Reconnect to new language
  setTimeout(() => {
    console.log("ðŸ“Š AFTER switch - Segments:", transcriptBox.children.length);
    console.log("ðŸ“Š AFTER switch - HTML length:", transcriptBox.innerHTML.length);
    connectSockets(lang);
    statusLabel.textContent = `Now listening in: ${lang}`;

  }, 150);
});