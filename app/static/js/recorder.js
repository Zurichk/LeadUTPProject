/**
 * Grabación del micrófono en formato WAV (PCM 16 kHz mono), el formato que
 * acepta Azure AI Speech para el reconocimiento por lotes.
 *
 * Se usa como respaldo cuando el navegador no soporta la Web Speech API
 * (por ejemplo, Safari o Firefox). La decodificación y el remuestreo se hacen
 * en el navegador con la Web Audio API, sin enviar nada a ningún servicio
 * externo hasta que la aplicación lo decide.
 */
(function (global) {
  "use strict";

  const TARGET_SAMPLE_RATE = 16000;

  function isSupported() {
    return Boolean(
      navigator.mediaDevices &&
        navigator.mediaDevices.getUserMedia &&
        global.AudioContext &&
        global.MediaRecorder
    );
  }

  function pickMimeType() {
    const candidates = [
      "audio/webm;codecs=opus",
      "audio/webm",
      "audio/mp4",
      "audio/ogg;codecs=opus",
    ];
    for (const type of candidates) {
      if (global.MediaRecorder.isTypeSupported(type)) {
        return type;
      }
    }
    return "";
  }

  /** Codifica un AudioBuffer mono en un blob WAV PCM 16 bits. */
  function encodeWav(audioBuffer) {
    const channelCount = audioBuffer.numberOfChannels;
    const frames = audioBuffer.length;
    const interleaved = new Float32Array(frames * channelCount);

    for (let frame = 0; frame < frames; frame += 1) {
      for (let channel = 0; channel < channelCount; channel += 1) {
        interleaved[frame * channelCount + channel] =
          audioBuffer.getChannelData(channel)[frame];
      }
    }

    const buffer = new ArrayBuffer(44 + interleaved.length * 2);
    const view = new DataView(buffer);
    const writeString = (offset, text) => {
      for (let index = 0; index < text.length; index += 1) {
        view.setUint8(offset + index, text.charCodeAt(index));
      }
    };

    writeString(0, "RIFF");
    view.setUint32(4, 36 + interleaved.length * 2, true);
    writeString(8, "WAVE");
    writeString(12, "fmt ");
    view.setUint32(16, 16, true);
    view.setUint16(20, 1, true);
    view.setUint16(22, channelCount, true);
    view.setUint32(24, audioBuffer.sampleRate, true);
    view.setUint32(
      28,
      audioBuffer.sampleRate * channelCount * 2,
      true
    );
    view.setUint16(32, channelCount * 2, true);
    view.setUint16(34, 16, true);
    writeString(36, "data");
    view.setUint32(40, interleaved.length * 2, true);

    let offset = 44;
    for (let index = 0; index < interleaved.length; index += 1) {
      const sample = Math.max(-1, Math.min(1, interleaved[index]));
      view.setInt16(offset, sample < 0 ? sample * 0x8000 : sample * 0x7fff, true);
      offset += 2;
    }

    return new Blob([view], { type: "audio/wav" });
  }

  /** Remuestrea el audio decodificado a mono 16 kHz. */
  async function resample(audioBuffer) {
    const frames = Math.ceil(audioBuffer.duration * TARGET_SAMPLE_RATE);
    const offline = new OfflineAudioContext(1, frames, TARGET_SAMPLE_RATE);
    const source = offline.createBufferSource();
    source.buffer = audioBuffer;
    source.connect(offline.destination);
    source.start();
    return offline.startRendering();
  }

  /**
   * Graba del micrófono y devuelve un blob WAV.
   *
   * @param {number} maxMs Duración máxima de la grabación.
   * @returns {Promise<Blob>} Audio listo para enviar a `/api/recognize-speech`.
   */
  async function recordWav(maxMs) {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mimeType = pickMimeType();
    const recorder = mimeType
      ? new MediaRecorder(stream, { mimeType })
      : new MediaRecorder(stream);
    const chunks = [];
    recorder.addEventListener("dataavailable", (event) => {
      if (event.data && event.data.size > 0) {
        chunks.push(event.data);
      }
    });
    recorder.start();

    try {
      await new Promise((resolve) => {
        const timer = setTimeout(() => {
          if (recorder.state !== "inactive") {
            recorder.stop();
          }
        }, maxMs);
        recorder.addEventListener(
          "stop",
          () => {
            clearTimeout(timer);
            resolve();
          },
          { once: true }
        );
      });
    } finally {
      stream.getTracks().forEach((track) => track.stop());
    }

    const raw = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
    if (raw.size === 0) {
      throw new Error("empty-audio");
    }

    const decodeContext = new (global.AudioContext || global.webkitAudioContext)();
    try {
      const decoded = await decodeContext.decodeAudioData(await raw.arrayBuffer());
      const mono = await resample(decoded);
      return encodeWav(mono);
    } finally {
      decodeContext.close();
    }
  }

  global.LecturaRecorder = {
    isSupported,
    recordWav,
  };
})(window);