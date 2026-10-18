/**
 * LecturaFácil — lógica de la interfaz infantil.
 *
 * Flujo de uso:
 * 1. Se elige perfil e idioma.
 * 2. Se sube (o se arrastra) la foto de la ficha → el backend la guarda en Blob
 *    Storage y devuelve las palabras detectadas por el OCR.
 * 3. Cada tarjeta permite escuchar la palabra (TTS de Azure AI Speech) y decirla
 *    con el micrófono (Web Speech API del navegador o, si no está disponible,
 *    Azure AI Speech en el servidor).
 * 4. El backend evalúa la pronunciación y la tarjeta se ilumina en verde si
 *    está bien.
 */
(function () {
  "use strict";

  const config = window.LECTURA || {};
  const catalogue = config.i18n || {};

  const state = {
    language: config.language || "es",
    profileId: null,
    words: [],
    results: new Map(),
    listeningCard: null,
    selectedAvatar: (config.avatars || ["👧"])[0],
    letterCase:
      window.localStorage.getItem("lectura.letterCase") || config.letterCase || "both",
  };

  const elements = {};

  /* ------------------------------------------------------------- utilidades */

  function t(key, params) {
    const template = catalogue[key] || key;
    if (!params) {
      return template;
    }
    return template.replace(/\{(\w+)\}/g, (match, name) =>
      Object.prototype.hasOwnProperty.call(params, name) ? params[name] : match
    );
  }

  function localeTag() {
    return state.language === "ca" ? "ca-ES" : "es-ES";
  }

  function withLanguage(path) {
    const separator = path.includes("?") ? "&" : "?";
    return `${path}${separator}lang=${encodeURIComponent(state.language)}`;
  }

  async function apiFetch(path, options) {
    const response = await fetch(withLanguage(path), options);
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      const error = new Error(
        (body && body.error && body.error.message) || t("error.generic")
      );
      error.code = body && body.error ? body.error.code : "http_error";
      throw error;
    }
    return response;
  }

  let toastTimer = null;
  function showToast(message) {
    elements.toast.textContent = message;
    elements.toast.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      elements.toast.hidden = true;
    }, 3200);
  }

  /* ------------------------------------------------------------------ audio */

  let audioContext = null;
  function getAudioContext() {
    if (!audioContext) {
      const Ctor = window.AudioContext || window.webkitAudioContext;
      audioContext = new Ctor();
    }
    if (audioContext.state === "suspended") {
      audioContext.resume();
    }
    return audioContext;
  }

  function playTone(frequency, startDelay, duration, gainValue) {
    const ctx = getAudioContext();
    const oscillator = ctx.createOscillator();
    const gain = ctx.createGain();
    oscillator.type = "sine";
    oscillator.frequency.value = frequency;
    const start = ctx.currentTime + startDelay;
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(gainValue, start + 0.03);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
    oscillator.connect(gain).connect(ctx.destination);
    oscillator.start(start);
    oscillator.stop(start + duration);
  }

  function playSuccessSound() {
    playTone(523.25, 0, 0.18, 0.25);
    playTone(659.25, 0.12, 0.18, 0.25);
    playTone(783.99, 0.24, 0.32, 0.3);
  }

  function playTryAgainSound() {
    playTone(392, 0, 0.2, 0.18);
    playTone(329.63, 0.16, 0.26, 0.16);
  }

  /**
   * Espera a que el navegador cargue la lista de voces (asíncrona en Chrome).
   *
   * @param {number} timeoutMs Tiempo máximo de espera.
   * @returns {Promise<SpeechSynthesisVoice[]>} Voces disponibles.
   */
  function waitForVoices(timeoutMs) {
    return new Promise((resolve) => {
      const current = window.speechSynthesis.getVoices();
      if (current.length) {
        resolve(current);
        return;
      }
      const onChange = () => {
        window.speechSynthesis.removeEventListener("voiceschanged", onChange);
        resolve(window.speechSynthesis.getVoices());
      };
      window.speechSynthesis.addEventListener("voiceschanged", onChange);
      setTimeout(() => resolve(window.speechSynthesis.getVoices()), timeoutMs);
    });
  }

  /** Elige la mejor voz disponible para el idioma de la ficha. */
  function pickVoice(voices, locale) {
    const normalized = locale.toLowerCase();
    const language = normalized.slice(0, 2);
    const exact = voices.filter((voice) => (voice.lang || "").toLowerCase() === normalized);
    const sameLanguage = voices.filter((voice) =>
      (voice.lang || "").toLowerCase().startsWith(language)
    );
    const pool = exact.length ? exact : sameLanguage;
    if (!pool.length) {
      return null;
    }
    return pool.find((voice) => voice.localService) || pool[0];
  }

  let azureVoiceAvailable = config.speechBackend !== "browser";

  function shouldTryAzureVoice() {
    if (config.speechBackend === "browser") {
      return false;
    }
    return azureVoiceAvailable;
  }

  async function speakWithBrowser(text) {
    if (!("speechSynthesis" in window)) {
      showToast(t("error.no_voice_available"));
      return false;
    }
    const locale = localeTag();
    const voices = await waitForVoices(1500);
    const voice = pickVoice(voices, locale);
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = locale;
    utterance.rate = 0.85;
    if (voice) {
      utterance.voice = voice;
    } else {
      showToast(t("error.no_voice_available"));
    }
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    return Boolean(voice);
  }

  const ttsCache = new Map();

  /** Escucha la palabra: intenta Azure Speech y, si no está, el navegador. */
  async function speakWord(word, language) {
    const cacheKey = `${language}:${word}`;
    if (shouldTryAzureVoice()) {
      let objectUrl = ttsCache.get(cacheKey);
      if (!objectUrl) {
        try {
          const response = await apiFetch("/api/tts", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ word, language }),
          });
          objectUrl = URL.createObjectURL(await response.blob());
          ttsCache.set(cacheKey, objectUrl);
        } catch (error) {
          azureVoiceAvailable = false;
          await speakWithBrowser(word);
          return;
        }
      }
      const audio = new Audio(objectUrl);
      audio.play().catch(() => speakWithBrowser(word));
      return;
    }
    await speakWithBrowser(word);
  }

  /** Reproduce el mensaje de refuerzo con la voz del servidor o del navegador. */
  async function speakFeedback(message) {
    if (shouldTryAzureVoice()) {
      const cacheKey = `feedback:${state.language}:${message}`;
      if (!ttsCache.has(cacheKey)) {
        try {
          const response = await apiFetch("/api/tts", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ word: message, language: state.language }),
          });
          ttsCache.set(cacheKey, URL.createObjectURL(await response.blob()));
        } catch (error) {
          azureVoiceAvailable = false;
          await speakWithBrowser(message);
          return;
        }
      }
      const audio = new Audio(ttsCache.get(cacheKey));
      audio.play().catch(() => speakWithBrowser(message));
      return;
    }
    await speakWithBrowser(message);
  }

  /* --------------------------------------------------------------- perfiles */

  function storedProfiles() {
    return config.profiles || [];
  }

  function renderProfiles() {
    const container = elements.profileList;
    container.textContent = "";
    storedProfiles().forEach((profile) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "profile-card";
      button.setAttribute("role", "listitem");
      button.dataset.profileId = profile.id;
      if (profile.id === state.profileId) {
        button.classList.add("is-active");
      }

      const avatar = document.createElement("span");
      avatar.className = "profile-card__avatar";
      avatar.textContent = profile.avatar;

      const name = document.createElement("span");
      name.textContent = profile.name;

      button.append(avatar, name);
      button.addEventListener("click", () => selectProfile(profile.id));
      container.append(button);
    });
  }

  function selectProfile(profileId) {
    state.profileId = profileId;
    window.localStorage.setItem("lectura.profile", profileId);
    renderProfiles();
  }

  function restoreProfile() {
    const stored = window.localStorage.getItem("lectura.profile");
    const profiles = storedProfiles();
    const match = profiles.find((profile) => profile.id === stored);
    state.profileId = match ? match.id : profiles.length ? profiles[0].id : null;
    renderProfiles();
  }

  function renderAvatarPicker() {
    const container = elements.profileAvatars;
    container.textContent = "";
    (config.avatars || []).forEach((avatar) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "avatar-option";
      button.textContent = avatar;
      button.setAttribute("role", "radio");
      button.setAttribute("aria-checked", avatar === state.selectedAvatar);
      button.classList.toggle("is-active", avatar === state.selectedAvatar);
      button.addEventListener("click", () => {
        state.selectedAvatar = avatar;
        renderAvatarPicker();
      });
      container.append(button);
    });
  }

  function openProfileModal() {
    elements.profileModal.hidden = false;
    elements.profileName.focus();
  }

  function closeProfileModal() {
    elements.profileModal.hidden = true;
  }

  async function saveProfile() {
    const name = elements.profileName.value.trim();
    if (!name) {
      showToast(t("error.generic"));
      return;
    }
    try {
      const response = await apiFetch("/api/profiles", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          avatar: state.selectedAvatar,
          language: state.language,
        }),
      });
      const profile = await response.json();
      config.profiles = (config.profiles || []).concat([profile]);
      closeProfileModal();
      elements.profileName.value = "";
      selectProfile(profile.id);
    } catch (error) {
      showToast(error.message);
    }
  }

  /* ----------------------------------------------------------------- subida */

  async function uploadSheet(file) {
    if (!file) {
      return;
    }
    if (!file.type.startsWith("image/")) {
      showToast(t("error.file_type"));
      return;
    }
    if (file.size > config.maxUploadMb * 1024 * 1024) {
      showToast(t("error.file_size", { max: config.maxUploadMb }));
      return;
    }

    elements.uploadStatus.textContent = t("upload.processing");
    elements.uploadPreview.src = URL.createObjectURL(file);
    elements.uploadPreview.hidden = false;

    const form = new FormData();
    form.append("file", file);
    form.append("language", "auto");
    form.append("max_words", String(config.defaultMaxWords));

    try {
      const response = await apiFetch("/api/upload-sheet", {
        method: "POST",
        body: form,
      });
      const sheet = await response.json();
      renderWords(sheet.words || []);
      elements.uploadStatus.textContent = "";
    } catch (error) {
      elements.uploadStatus.textContent = "";
      showToast(error.message);
    }
  }

  /* --------------------------------------------------------------- tarjetas */

  function renderWords(words) {
    state.words = words;
    state.results.clear();
    elements.wordsGrid.textContent = "";

    if (!words.length) {
      const empty = document.createElement("p");
      empty.className = "words__empty";
      empty.textContent = t("sheet.empty");
      elements.wordsGrid.append(empty);
      elements.resetButton.hidden = true;
      updateTranslateButton();
      updateProgress();
      return;
    }

    words.forEach((word, index) => elements.wordsGrid.append(buildCard(word, index)));
    elements.resetButton.hidden = false;
    updateProgress();
    updateTranslateButton();
    paintTranslations();
  }

  /**
   * Pinta la palabra en el modo de letras elegido: solo mayúsculas, solo
   * minúsculas o las dos (mayúscula grande y minúscula debajo).
   *
   * @param {HTMLElement} element Contenedor del texto de la tarjeta.
   * @param {string} word Palabra original de la ficha.
   * @param {string} mode "upper", "lower" o "both".
   */
  function renderWordText(element, word, mode) {
    element.textContent = "";
    if (mode === "upper") {
      element.classList.add("word-card__text--single");
      element.textContent = word.toLocaleUpperCase(state.language);
      return;
    }
    if (mode === "lower") {
      element.classList.add("word-card__text--single");
      element.textContent = word.toLocaleLowerCase(state.language);
      return;
    }
    element.classList.remove("word-card__text--single");
    const upper = document.createElement("span");
    upper.className = "word-card__upper";
    upper.textContent = word.toLocaleUpperCase(state.language);
    const lower = document.createElement("span");
    lower.className = "word-card__lower";
    lower.textContent = word.toLocaleLowerCase(state.language);
    element.append(upper, lower);
  }

  function applyLetterCaseToAll() {
    state.words.forEach((word, index) => {
      const element = document.querySelector(
        `.word-card[data-word-index="${index}"] .word-card__text`
      );
      if (element) {
        renderWordText(element, word.text, state.letterCase);
      }
    });
    document.querySelectorAll("[data-case]").forEach((button) => {
      const active = button.dataset.case === state.letterCase;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", active ? "true" : "false");
    });
  }

  function buildCard(word, index) {
    const card = document.createElement("article");
    card.className = "word-card";
    card.dataset.wordIndex = String(index);
    card.dataset.word = word.text;

    const text = document.createElement("p");
    text.className = "word-card__text";
    renderWordText(text, word.text, state.letterCase);

    const actions = document.createElement("div");
    actions.className = "word-card__actions";

    const listenButton = document.createElement("button");
    listenButton.type = "button";
    listenButton.className = "word-button word-button--listen";
    listenButton.textContent = "🔊";
    listenButton.setAttribute("aria-label", t("card.listen"));
    listenButton.addEventListener("click", () => {
      speakWord(word.text, word.language || state.language).catch(() =>
        showToast(t("error.generic"))
      );
    });

    const speakButton = document.createElement("button");
    speakButton.type = "button";
    speakButton.className = "word-button word-button--speak";
    speakButton.textContent = "🎤";
    speakButton.setAttribute("aria-label", t("card.speak"));
    speakButton.addEventListener("click", () => handleSpeaking(card, word));

    const feedback = document.createElement("p");
    feedback.className = "word-card__feedback";

    const translated = document.createElement("p");
    translated.className = "word-card__translation";
    translated.hidden = true;

    actions.append(listenButton, speakButton);
    card.append(text, translated, actions, feedback);
    return card;
  }

  function setCardState(card, stateName, message) {
    card.classList.remove("is-correct", "is-try-again");
    if (stateName) {
      card.classList.add(stateName);
    }
    const feedback = card.querySelector(".word-card__feedback");
    feedback.textContent = message || "";
    feedback.classList.remove("is-success", "is-error");
    if (stateName === "is-correct") {
      feedback.classList.add("is-success");
    } else if (stateName === "is-try-again") {
      feedback.classList.add("is-error");
    }
  }

  function updateProgress() {
    const total = state.words.length;
    const done = state.results.size;
    elements.wordsProgress.textContent = total
      ? `${done} / ${total}`
      : "";
    if (total > 0 && done === total) {
      celebrate();
    }
  }

  /* ------------------------------------------------------------- evaluación */

  /**
   * Pregunta al backend si alguna de las transcripciones corresponde a la
   * palabra esperada.
   *
   * @param {string} expectedWord Palabra de la tarjeta.
   * @param {string[]} candidates Transcripciones candidatas.
   * @returns {Promise<object>} Primer resultado correcto o el último evaluado.
   */
  async function evaluate(expectedWord, candidates) {
    let lastResult = null;
    for (const candidate of candidates) {
      const response = await apiFetch("/api/evaluate-speech", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          expected_word: expectedWord,
          spoken_text: candidate,
          language: state.language,
        }),
      });
      lastResult = await response.json();
      if (lastResult.correct) {
        return lastResult;
      }
    }
    return lastResult;
  }

  function applyEvaluation(card, result, index) {
    state.results.set(index, result);
    if (result.correct) {
      setCardState(card, "is-correct", result.message);
      playSuccessSound();
      speakFeedback(result.message);
    } else {
      setCardState(card, "is-try-again", result.message);
      playTryAgainSound();
      setTimeout(() => setCardState(card, "", ""), 2200);
    }
    updateProgress();
  }

  async function evaluateCandidates(card, word, index, candidates) {
    if (!candidates.length) {
      setCardState(card, "", "");
      showToast(t("error.empty_audio"));
      return;
    }
    try {
      const result = await evaluate(word.text, candidates);
      if (result) {
        applyEvaluation(card, result, index);
        return;
      }
      setCardState(card, "", "");
    } catch (error) {
      setCardState(card, "", "");
      showToast(error.message);
    }
  }

  /* ------------------------------------------------------------ micrófono */

  function browserRecognition() {
    const Ctor =
      window.SpeechRecognition || window.webkitSpeechRecognition || null;
    if (!Ctor) {
      return null;
    }
    const recognition = new Ctor();
    recognition.lang = localeTag();
    recognition.interimResults = false;
    recognition.maxAlternatives = 5;
    recognition.continuous = false;
    return recognition;
  }

  function cardIndex(card) {
    return Number(card.dataset.wordIndex || "0");
  }

  async function recognizeWithServer(card, word, index) {
    if (!window.LecturaRecorder || !window.LecturaRecorder.isSupported()) {
      setCardState(card, "", "");
      showToast(t("error.generic"));
      return;
    }
    try {
      const blob = await window.LecturaRecorder.recordWav(4000);
      const form = new FormData();
      form.append("file", blob, "audio.wav");
      form.append("language", word.language || state.language);
      const response = await apiFetch("/api/recognize-speech", {
        method: "POST",
        body: form,
      });
      const payload = await response.json();
      await evaluateCandidates(card, word, index, [payload.text]);
    } catch (error) {
      setCardState(card, "", "");
      showToast(
        error.code === "speech_not_configured"
          ? t("error.no_microphone_support")
          : error.message
      );
    }
  }

  function handleSpeaking(card, word) {
    if (state.listeningCard) {
      return;
    }
    const index = cardIndex(card);
    const speakButton = card.querySelector(".word-button--speak");
    state.listeningCard = card;
    card.classList.add("is-listening");
    speakButton.classList.add("is-listening");
    setCardState(card, "", t("card.listening"));

    const finish = () => {
      state.listeningCard = null;
      card.classList.remove("is-listening");
      speakButton.classList.remove("is-listening");
    };

    const recognition = browserRecognition();
    if (!recognition) {
      finish();
      recognizeWithServer(card, word, index);
      return;
    }

    let settled = false;
    recognition.addEventListener("result", (event) => {
      if (settled) {
        return;
      }
      settled = true;
      finish();
      const result = event.results[0];
      const alternatives = [];
      for (let position = 0; position < result.length; position += 1) {
        alternatives.push(result[position].transcript.trim());
      }
      evaluateCandidates(card, word, index, alternatives);
    });
    recognition.addEventListener("error", (event) => {
      if (settled) {
        return;
      }
      settled = true;
      finish();
      if (event.error === "no-speech") {
        setCardState(card, "", "");
        showToast(t("error.empty_audio"));
        return;
      }
      recognizeWithServer(card, word, index);
    });
    recognition.addEventListener("end", () => {
      if (settled) {
        return;
      }
      settled = true;
      finish();
      recognizeWithServer(card, word, index);
    });

    try {
      recognition.start();
    } catch (error) {
      finish();
      recognizeWithServer(card, word, index);
    }
  }

  /* ------------------------------------------------------------ traducción */

  const translations = new Map();

  function targetLanguageFor(source) {
    return source === "ca" ? "es" : "ca";
  }

  function updateTranslateButton() {
    if (!config.translationEnabled || !state.words.length) {
      elements.translateButton.hidden = true;
      return;
    }
    elements.translateButton.hidden = false;
    const source = state.words[0].language || state.language;
    elements.translateLabel.textContent =
      source === "ca" ? t("translate.button_reverse") : t("translate.button");
  }

  function paintTranslations() {
    state.words.forEach((word) => {
      const translated = translations.get(word.text.toLocaleLowerCase());
      const element = document.querySelector(
        `.word-card[data-word="${CSS.escape(word.text)}"] .word-card__translation`
      );
      if (element) {
        element.textContent = translated || "";
        element.hidden = !translated;
      }
    });
  }

  async function translateWords() {
    if (!state.words.length) {
      return;
    }
    const source = state.words[0].language || state.language;
    const target = targetLanguageFor(source);
    elements.translateButton.disabled = true;
    elements.translateLabel.textContent = t("translate.loading");
    try {
      const response = await apiFetch("/api/translate-words", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          words: state.words.map((word) => word.text),
          source_language: source,
          target_language: target,
        }),
      });
      const payload = await response.json();
      payload.translations.forEach((item) => {
        translations.set(item.word.toLocaleLowerCase(), item.translated);
      });
      paintTranslations();
      showToast(t("translate.done"));
    } catch (error) {
      showToast(
        error.code === "translation_not_configured"
          ? t("translate.unavailable")
          : error.message
      );
    } finally {
      elements.translateButton.disabled = false;
      updateTranslateButton();
    }
  }

  /* ---------------------------------------------------------------- confeti */

  function celebrate() {
    const canvas = elements.confetti;
    const context = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    canvas.width = window.innerWidth * dpr;
    canvas.height = window.innerHeight * dpr;
    context.setTransform(dpr, 0, 0, dpr, 0, 0);

    const colors = ["#ff7ab8", "#7c4dff", "#22c55e", "#ffd166", "#60a5fa"];
    const particles = Array.from({ length: 140 }, () => ({
      x: Math.random() * window.innerWidth,
      y: -20 - Math.random() * 200,
      size: 6 + Math.random() * 8,
      speed: 2 + Math.random() * 4,
      drift: (Math.random() - 0.5) * 1.5,
      color: colors[Math.floor(Math.random() * colors.length)],
    }));

    canvas.classList.add("is-active");
    speakFeedback(
      t("confetti.title", { count: state.words.length })
    );

    let frame = 0;
    const totalFrames = 260;
    function draw() {
      frame += 1;
      context.clearRect(0, 0, canvas.width, canvas.height);
      particles.forEach((particle) => {
        particle.y += particle.speed;
        particle.x += particle.drift;
        context.fillStyle = particle.color;
        context.fillRect(particle.x, particle.y, particle.size, particle.size * 1.6);
      });
      if (frame < totalFrames) {
        window.requestAnimationFrame(draw);
      } else {
        canvas.classList.remove("is-active");
        context.clearRect(0, 0, canvas.width, canvas.height);
      }
    }
    window.requestAnimationFrame(draw);
  }

  /* ----------------------------------------------------------------- eventos */

  function bindEvents() {
    const fileInput = elements.fileInput;
    fileInput.addEventListener("change", () => {
      if (fileInput.files && fileInput.files.length) {
        uploadSheet(fileInput.files[0]);
        fileInput.value = "";
      }
    });

    const dropzone = elements.dropzone;
    ["dragenter", "dragover"].forEach((eventName) => {
      dropzone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropzone.classList.add("is-dragging");
      });
    });
    ["dragleave", "drop"].forEach((eventName) => {
      dropzone.addEventListener(eventName, (event) => {
        event.preventDefault();
        dropzone.classList.remove("is-dragging");
      });
    });
    dropzone.addEventListener("drop", (event) => {
      const file = event.dataTransfer && event.dataTransfer.files[0];
      if (file) {
        uploadSheet(file);
      }
    });

    elements.resetButton.addEventListener("click", () => {
      renderWords([]);
      elements.uploadPreview.hidden = true;
    });

    elements.translateButton.addEventListener("click", translateWords);

    elements.addProfileButton.addEventListener("click", openProfileModal);
    elements.profileCancel.addEventListener("click", closeProfileModal);
    elements.profileSave.addEventListener("click", saveProfile);
    elements.profileModal.addEventListener("click", (event) => {
      if (event.target === elements.profileModal) {
        closeProfileModal();
      }
    });
    elements.profileName.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        saveProfile();
      }
    });

    document.querySelectorAll("[data-case]").forEach((button) => {
      button.addEventListener("click", () => {
        state.letterCase = button.dataset.case;
        window.localStorage.setItem("lectura.letterCase", state.letterCase);
        applyLetterCaseToAll();
      });
    });

    document.querySelectorAll("[data-language]").forEach((button) => {
      button.addEventListener("click", () => {
        const language = button.dataset.language;
        document.cookie = `lang=${language}; path=/; max-age=31536000; samesite=lax`;
        window.location.assign(withLanguage("/"));
      });
    });
  }

  /* ------------------------------------------------------------------- init */

  function init() {
    elements.fileInput = document.getElementById("file-input");
    elements.dropzone = document.getElementById("dropzone");
    elements.uploadStatus = document.getElementById("upload-status");
    elements.uploadPreview = document.getElementById("sheet-preview");
    elements.wordsGrid = document.getElementById("words-grid");
    elements.wordsProgress = document.getElementById("words-progress");
    elements.resetButton = document.getElementById("reset-button");
    elements.profileList = document.getElementById("profile-list");
    elements.addProfileButton = document.getElementById("add-profile-button");
    elements.profileModal = document.getElementById("profile-modal");
    elements.profileName = document.getElementById("profile-name");
    elements.profileAvatars = document.getElementById("profile-avatars");
    elements.profileCancel = document.getElementById("profile-cancel");
    elements.profileSave = document.getElementById("profile-save");
    elements.toast = document.getElementById("toast");
    elements.confetti = document.getElementById("confetti");
    elements.translateButton = document.getElementById("translate-button");
    elements.translateLabel = document.getElementById("translate-label");

    restoreProfile();
    renderAvatarPicker();
    applyLetterCaseToAll();
    bindEvents();
  }

  document.addEventListener("DOMContentLoaded", init);
})();