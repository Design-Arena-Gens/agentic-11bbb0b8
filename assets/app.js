(() => {
  const conversationEl = document.querySelector("#conversation");
  const intelEl = document.querySelector("#intel-feed ul");
  const statusIndicator = document.querySelector(".status-indicator");
  const statusCopy = document.querySelector(".status-copy");
  const form = document.querySelector("#command-form");
  const input = document.querySelector("#command-input");
  const voiceToggle = document.querySelector("#voice-toggle");
  const messageTemplate = document.querySelector("#message-template");

  const state = {
    history: [],
    isProcessing: false,
    recognition: null,
    voiceEnabled: false,
    speechPending: false,
  };

  const synth = window.speechSynthesis;

  const scrollConversationToEnd = () => {
    requestAnimationFrame(() => {
      conversationEl.scrollTo({
        top: conversationEl.scrollHeight,
        behavior: "smooth",
      });
    });
  };

  const updateStatus = (status, copy) => {
    statusIndicator.dataset.status = status;
    statusCopy.textContent = copy;
  };

  const renderMessage = ({ role, content, speaking = false }) => {
    const clone = messageTemplate.content.firstElementChild.cloneNode(true);
    clone.classList.add(role === "assistant" ? "assistant" : role);
    if (state.isProcessing && role === "assistant" && speaking) {
      clone.classList.add("thinking");
    }
    const avatar = clone.querySelector(".avatar");
    avatar.textContent = role === "user" ? "You" : role === "assistant" ? "J" : "SYS";
    if (role === "assistant") avatar.textContent = "J";
    clone.querySelector("p").textContent = content;
    conversationEl.appendChild(clone);
    scrollConversationToEnd();
    return clone;
  };

  const speak = (text) => {
    if (!synth) return;
    synth.cancel();
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.rate = 1.02;
    utterance.pitch = 1.05;
    utterance.lang = "en-US";
    const voices = synth.getVoices();

    const preferredVoices = [
      /jarvis/i,
      /brian/i,
      /matthew/i,
      /guy/i,
      /en-us/i,
    ];

    const voice =
      voices.find((v) => preferredVoices.some((pattern) => pattern.test(v.name))) ||
      voices.find((v) => /en-GB/i.test(v.lang)) ||
      voices[0];

    if (voice) utterance.voice = voice;
    synth.speak(utterance);
  };

  const pushIntel = (items = []) => {
    if (!items.length) return;
    intelEl.replaceChildren();
    items.forEach((item) => {
      const li = document.createElement("li");
      li.textContent = item;
      intelEl.appendChild(li);
    });
  };

  const persistHistory = () => {
    try {
      const payload = JSON.stringify(state.history.slice(-20));
      localStorage.setItem("jarvis_history", payload);
    } catch {
      /* noop */
    }
  };

  const restoreHistory = () => {
    try {
      const raw = localStorage.getItem("jarvis_history");
      if (!raw) return;
      const parsed = JSON.parse(raw);
      state.history = Array.isArray(parsed) ? parsed : [];
      state.history.forEach((item) => renderMessage(item));
      if (state.history.length) {
        pushIntel(
          [
            "Historical context restored.",
            `Loaded ${state.history.length} transmissions.`,
            "Jarvis is ready to continue the mission.",
          ].concat(
            state.history
              .slice(-3)
              .map((entry) => `${entry.role === "user" ? "You" : "Jarvis"}: ${entry.content}`)
          )
        );
      }
    } catch {
      state.history = [];
    }
  };

  const toggleVoiceInput = () => {
    if (!("webkitSpeechRecognition" in window || "SpeechRecognition" in window)) {
      voiceToggle.disabled = true;
      voiceToggle.title = "Voice recognition not supported in this browser.";
      return;
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!state.recognition) {
      const recognition = new SpeechRecognition();
      recognition.lang = "en-US";
      recognition.interimResults = false;
      recognition.continuous = false;
      recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript.trim();
        if (transcript) {
          input.value = transcript;
          form.dispatchEvent(new Event("submit", { cancelable: true }));
        }
      };
      recognition.onstart = () => {
        voiceToggle.classList.add("active");
        updateStatus("thinking", "Listening");
      };
      recognition.onend = () => {
        voiceToggle.classList.remove("active");
        if (!state.isProcessing) updateStatus("idle", "Systems Idle");
      };
      recognition.onerror = () => {
        voiceToggle.classList.remove("active");
        if (!state.isProcessing) updateStatus("idle", "Systems Idle");
      };
      state.recognition = recognition;
    }

    if (state.voiceEnabled) {
      state.recognition.stop();
      state.voiceEnabled = false;
      voiceToggle.classList.remove("active");
      updateStatus("idle", "Voice Link Offline");
    } else {
      state.recognition.start();
      state.voiceEnabled = true;
    }
  };

  const sendCommand = async (message) => {
    if (!message || state.isProcessing) return;
    const trimmed = message.trim();
    if (!trimmed) return;

    state.isProcessing = true;
    updateStatus("thinking", "Processing");

    const userPayload = { role: "user", content: trimmed };
    state.history.push(userPayload);
    renderMessage(userPayload);
    persistHistory();
    input.value = "";

    const placeholder = renderMessage({
      role: "assistant",
      content: "•••",
      speaking: true,
    });

    try {
      const response = await fetch("/api/assistant", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: trimmed,
          history: state.history.slice(-12),
        }),
      });

      if (!response.ok) {
        throw new Error(`Request failed with status ${response.status}`);
      }

      const data = await response.json();
      const assistantPayload = {
        role: "assistant",
        content: data.reply || "I'm here.",
      };

      state.history.push(assistantPayload);
      conversationEl.removeChild(placeholder);
      renderMessage(assistantPayload);
      persistHistory();

      if (Array.isArray(data.actions) && data.actions.length) {
        pushIntel(data.actions);
      }

      if (data.intent) {
        statusCopy.textContent = `Intent: ${data.intent}`;
      }

      if (data.speak !== false) {
        speak(assistantPayload.content);
      }
    } catch (error) {
      conversationEl.removeChild(placeholder);
      renderMessage({
        role: "assistant",
        content:
          "Systems encountered turbulence processing that request. Review logs and try again.",
      });
      console.error("Jarvis error:", error);
      pushIntel(["Error encountered.", error.message || String(error)]);
    } finally {
      state.isProcessing = false;
      if (state.voiceEnabled) {
        updateStatus("thinking", "Listening");
      } else {
        updateStatus("idle", "Systems Idle");
      }
    }
  };

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    sendCommand(input.value);
  });

  voiceToggle.addEventListener("click", () => {
    toggleVoiceInput();
  });

  document.querySelectorAll("[data-command]").forEach((button) => {
    button.addEventListener("click", () => {
      const command = button.dataset.command;
      input.value = command;
      form.dispatchEvent(new Event("submit", { cancelable: true }));
    });
  });

  window.addEventListener("load", () => {
    restoreHistory();
    if (!("speechSynthesis" in window)) {
      pushIntel(["Speech synthesis unavailable on this device."]);
    } else {
      // Preload voices
      if (typeof synth?.getVoices === "function") synth.getVoices();
    }
    if (!("webkitSpeechRecognition" in window || "SpeechRecognition" in window)) {
      voiceToggle.disabled = true;
      voiceToggle.title = "Voice recognition requires Chrome or Edge desktop.";
    }
  });
})();
