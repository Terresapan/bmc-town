import ApiService from "../services/ApiService";
import WebSocketApiService from "../services/WebSocketApiService";
import SuggestionManager from "./SuggestionManager";

class DialogueManager {
  constructor(scene) {
    // Core properties
    this.scene = scene;
    this.dialogueBox = null;
    this.activePhilosopher = null;

    // State management
    this.isTyping = false;
    this.isStreaming = false;
    this.isStreaming = false;
    // Connection management
    this.hasSetupListeners = false;
    this.disconnectTimeout = null;

    // Game mode and user context
    this.gameMode = "legacy";
    this.userToken = null;
    
    // Suggestion manager for proactive suggestions
    this.suggestionManager = null;
  }

  // === Initialization ===

  initialize(dialogueBox, gameMode = "legacy", userToken = null) {
    this.dialogueBox = dialogueBox;
    this.gameMode = gameMode;
    this.userToken = userToken;
    
    // Initialize SuggestionManager for business mode
    if (gameMode === "business" && userToken) {
      this.suggestionManager = new SuggestionManager(userToken);
    }

    if (!this.hasSetupListeners) {
      this.setupGlobalKeys();
      this.hasSetupListeners = true;
    }
  }

  setupGlobalKeys() {
    this.scene.input.keyboard.on("keydown", async (event) => {
      // Handle ESC key to close dialogue
      if (event.key === "Escape" && this.dialogueBox.isVisible()) {
        this.closeDialogue();
        return;
      }
      
      // Handle Enter key for submission (when textarea is focused)
      // Note: We check document.activeElement because Phaser captures global keys too
      if (event.key === "Enter" && !event.shiftKey && this.dialogueBox.isVisible() && this.isTyping) {
          // Prevent default newline if needed, though usually handled by preventing default on the textarea keydown
          // But here we just trigger the send.
          // Getting value from textarea
          this.currentMessage = this.dialogueBox.getValue();
          await this.handleEnterKey();
      }
    });

    // We also need to listen for keydown ON the textarea element itself to prevent default Enter behavior (newline)
    if (this.dialogueBox.textarea) {
        this.dialogueBox.textarea.addEventListener('keydown', async (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault(); // Prevent newline
                this.currentMessage = this.dialogueBox.getValue();
                await this.handleEnterKey();
            } else if (e.key === ' ' && !this.isTyping) {
                // If space is pressed and we're not typing, clear the text/continue
                e.preventDefault();
                this.continueDialogue();
            }
        });
    }
  }

  // === Input Handling ===
  // Native input handling via textarea, no custom key processing needed


  async handleEnterKey() {
    if (this.currentMessage.trim() !== "") {
      this.dialogueBox.show("...", true); // Show '...' while thinking/connecting

      if (this.activePhilosopher.defaultMessage) {
        await this.handleDefaultMessage();
      } else {
        await this.handleWebSocketMessage();
      }

      this.currentMessage = "";
      this.isTyping = false;
    } else if (!this.isTyping) {
      this.restartTypingPrompt();
    }
  }

  // === Message Processing ===

  async handleDefaultMessage() {
    const apiResponse = this.activePhilosopher.defaultMessage;
    this.dialogueBox.show("", true);
    await this.streamText(apiResponse);
  }

  async handleWebSocketMessage() {
    this.dialogueBox.show("", true);
    this.isStreaming = true;
    this.streamingText = "";

    try {
      // For business mode, use API streaming directly instead of WebSocket
      if (this.gameMode === "business") {
        await this.handleBusinessStream();
      } else {
        await this.processWebSocketMessage();
      }
    } catch (error) {
      console.error("Communication error:", error);
      await this.fallbackToRegularApi();
    } finally {
      this.isTyping = false;
    }
  }

  async handleBusinessStream() {
    this.isStreaming = true;
    this.streamingText = "";
    let proactiveSuggestion = null;
    
    await ApiService.streamBusinessMessage(
      this.activePhilosopher,
      this.currentMessage,
      this.userToken,
      (chunk) => {
        this.streamingText += chunk;
        this.dialogueBox.show(this.streamingText, true);
      },
      (suggestion) => {
        // Capture proactive suggestion from the stream
        proactiveSuggestion = suggestion;
        console.log("💡 Proactive Suggestion Received:", suggestion);
      }
    );
    
    this.finishStreaming();
    
    // Display proactive suggestion via SuggestionManager
    if (proactiveSuggestion && proactiveSuggestion.suggestion && this.suggestionManager) {
      this.suggestionManager.addSuggestion(proactiveSuggestion);
    }
  }

  // NOTE: Proactive suggestion tooltip methods have been moved to SuggestionManager.js
  // The SuggestionManager handles popup display, badge, inbox, and accept/dismiss actions.

  async processWebSocketMessage() {
    // Use appropriate WebSocket endpoint based on game mode
    const wsEndpoint =
      this.gameMode === "business" ? "/ws/chat/business" : "/ws/chat";
    await WebSocketApiService.connect(wsEndpoint);

    const callbacks = {
      onMessage: () => {
        this.finishStreaming();
      },
      onChunk: (chunk) => {
        this.streamingText += chunk;
        this.dialogueBox.show(this.streamingText, true);
      },
      onStreamingStart: () => {
        this.isStreaming = true;
      },
      onStreamingEnd: () => {
        this.finishStreaming();
      },
    };

    if (this.gameMode === "business") {
      await WebSocketApiService.sendBusinessMessage(
        this.activePhilosopher,
        this.currentMessage,
        this.userToken,
        callbacks
      );
    } else {
      await WebSocketApiService.sendMessage(
        this.activePhilosopher,
        this.currentMessage,
        callbacks
      );
    }

    while (this.isStreaming) {
      await new Promise((resolve) => setTimeout(resolve, 100));
    }

    this.currentMessage = "";
    WebSocketApiService.disconnect();
  }

  finishStreaming() {
    this.isStreaming = false;
    this.dialogueBox.show(this.streamingText, true);
  }

  async fallbackToRegularApi() {
    let apiResponse;

    if (this.gameMode === "business") {
      apiResponse = await ApiService.sendBusinessMessage(
        this.activePhilosopher,
        this.currentMessage,
        this.userToken
      );
    } else {
      apiResponse = await ApiService.sendMessage(
        this.activePhilosopher,
        this.currentMessage
      );
    }

    await this.streamText(apiResponse);
  }

  // === UI Management ===

  updateDialogueText() {
    // No-op: Native textarea handles its own display
  }

  restartTypingPrompt() {
    this.currentMessage = "";
    this.dialogueBox.show("", true); // Show empty editable box calling .focus() via show(..., true)
  }

  // === Cursor Management ===
  // Deprecated: Native cursor used
  stopCursorBlink() {}
  startCursorBlink() {}

  // === Dialogue Flow Control ===

  startDialogue(philosopher) {
    this.cancelDisconnectTimeout();

    // NOTE: Files now persist across expert switches for better UX
    // Users upload files once and can discuss with all business experts
    // To clear files, users can upload new files or use a manual reset function

    this.activePhilosopher = philosopher;
    this.isTyping = true;
    this.currentMessage = "";

    this.dialogueBox.show("", true); // Show empty editable box
  }

  clearUploadedPdf() {
    // Clear business-specific PDF data from all global variables when starting new conversation
    console.log(
      "SECURITY: Clearing all business-specific PDF data for new conversation"
    );

    // Clear legacy non-business-specific variables for backward compatibility
    if (window.tempBusinessPdf) {
      console.log("SECURITY: Clearing legacy PDF variable tempBusinessPdf");
      window.tempBusinessPdf = null;
      window.tempBusinessPdfName = null;
    }

    // Clear all business-specific PDF variables
    Object.keys(window).forEach((key) => {
      if (
        key.startsWith("tempBusinessPdf_") ||
        key.startsWith("tempBusinessPdfName_")
      ) {
        console.log(`SECURITY: Clearing business-specific PDF variable ${key}`);
        window[key] = null;
      }
    });
  }

  clearUploadedImage() {
    // Clear business-specific image data from all global variables when starting new conversation
    console.log(
      "SECURITY: Clearing all business-specific image data for new conversation"
    );

    // Clear legacy non-business-specific variable for backward compatibility
    if (window.tempBusinessImage) {
      console.log("SECURITY: Clearing legacy image variable tempBusinessImage");
      window.tempBusinessImage = null;
      window.tempBusinessImageName = null;
    }

    // Clear all business-specific image variables
    Object.keys(window).forEach((key) => {
      if (
        key.startsWith("tempBusinessImage_") ||
        key.startsWith("tempBusinessImageName_")
      ) {
        console.log(
          `SECURITY: Clearing business-specific image variable ${key}`
        );
        window[key] = null;
      }
    });
  }

  closeDialogue() {
    this.dialogueBox.hide();
    this.isTyping = false;
    this.currentMessage = "";
    this.isStreaming = false;

    this.scheduleDisconnect();
  }

  isInDialogue() {
    return this.dialogueBox && this.dialogueBox.isVisible();
  }

  continueDialogue() {
    if (!this.dialogueBox.isVisible()) return;

    if (this.isStreaming) {
      this.skipStreaming();
    } else if (!this.isTyping) {
      this.isTyping = true;
      this.currentMessage = "";
      this.restartTypingPrompt();
    }
  }

  // === Text Streaming ===

  async streamText(text, speed = 30) {
    this.isStreaming = true;
    let displayedText = "";

    for (let i = 0; i < text.length; i++) {

      displayedText += text[i];
      this.dialogueBox.show(displayedText, true);

      await new Promise((resolve) => setTimeout(resolve, speed));

      if (!this.isStreaming) break;
    }

    if (this.isStreaming) {
      this.dialogueBox.show(text, true);
    }

    this.isStreaming = false;
    return true;
  }

  skipStreaming() {
    this.isStreaming = false;
  }

  // === Connection Management ===

  cancelDisconnectTimeout() {
    if (this.disconnectTimeout) {
      clearTimeout(this.disconnectTimeout);
      this.disconnectTimeout = null;
    }
  }

  scheduleDisconnect() {
    this.cancelDisconnectTimeout();

    this.disconnectTimeout = setTimeout(() => {
      WebSocketApiService.disconnect();
    }, 5000);
  }

}

export default DialogueManager;
