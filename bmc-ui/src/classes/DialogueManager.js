import ApiService from "../services/ApiService";
import WebSocketApiService from "../services/WebSocketApiService";

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
  }

  // === Initialization ===

  initialize(dialogueBox, gameMode = "legacy", userToken = null) {
    this.dialogueBox = dialogueBox;
    this.gameMode = gameMode;
    this.userToken = userToken;

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
    
    // Display proactive suggestion tooltip if we received one
    if (proactiveSuggestion && proactiveSuggestion.suggestion) {
      this.showProactiveSuggestionTooltip(proactiveSuggestion);
    }
  }

  /**
   * Shows a tooltip with a proactive cross-canvas suggestion.
   * @param {Object} suggestion - The suggestion object with suggestion text and targetBlock.
   */
  showProactiveSuggestionTooltip(suggestion) {
    // Remove any existing tooltip first
    this.hideProactiveSuggestionTooltip();
    
    // Create tooltip element
    const tooltip = document.createElement("div");
    tooltip.id = "proactive-suggestion-tooltip";
    tooltip.className = "proactive-tooltip";
    tooltip.innerHTML = `
      <div class="proactive-tooltip-icon">💡</div>
      <div class="proactive-tooltip-content">
        <div class="proactive-tooltip-label">Canvas Advisor</div>
        <div class="proactive-tooltip-text">${suggestion.suggestion}</div>
        ${suggestion.targetBlock ? `<div class="proactive-tooltip-target">→ ${this.formatBlockName(suggestion.targetBlock)}</div>` : ""}
      </div>
      <button class="proactive-tooltip-close" onclick="document.getElementById('proactive-suggestion-tooltip').remove()">×</button>
    `;
    
    // Add styles if not already present
    if (!document.getElementById("proactive-tooltip-styles")) {
      const style = document.createElement("style");
      style.id = "proactive-tooltip-styles";
      style.textContent = `
        .proactive-tooltip {
          position: fixed;
          top: 20px;
          right: 20px;
          max-width: 350px;
          background: linear-gradient(135deg, rgba(45, 55, 72, 0.95) 0%, rgba(26, 32, 44, 0.95) 100%);
          border: 1px solid rgba(99, 179, 237, 0.4);
          border-radius: 12px;
          padding: 16px 20px;
          display: flex;
          align-items: flex-start;
          gap: 12px;
          box-shadow: 0 10px 40px rgba(0, 0, 0, 0.4), 0 0 20px rgba(99, 179, 237, 0.15);
          z-index: 10000;
          animation: slideInRight 0.4s ease-out, fadeOut 0.5s ease-out 8s forwards;
          font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
        }
        
        @keyframes slideInRight {
          from { transform: translateX(100px); opacity: 0; }
          to { transform: translateX(0); opacity: 1; }
        }
        
        @keyframes fadeOut {
          from { opacity: 1; }
          to { opacity: 0; }
        }
        
        .proactive-tooltip-icon {
          font-size: 28px;
          line-height: 1;
          flex-shrink: 0;
        }
        
        .proactive-tooltip-content {
          flex: 1;
        }
        
        .proactive-tooltip-label {
          font-size: 11px;
          font-weight: 600;
          text-transform: uppercase;
          letter-spacing: 0.5px;
          color: rgba(99, 179, 237, 0.9);
          margin-bottom: 6px;
        }
        
        .proactive-tooltip-text {
          font-size: 14px;
          line-height: 1.5;
          color: rgba(255, 255, 255, 0.95);
        }
        
        .proactive-tooltip-target {
          font-size: 12px;
          color: rgba(154, 230, 180, 0.9);
          margin-top: 8px;
          padding-top: 8px;
          border-top: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .proactive-tooltip-close {
          background: none;
          border: none;
          color: rgba(255, 255, 255, 0.5);
          font-size: 20px;
          cursor: pointer;
          padding: 0;
          line-height: 1;
          transition: color 0.2s;
        }
        
        .proactive-tooltip-close:hover {
          color: rgba(255, 255, 255, 0.9);
        }
      `;
      document.head.appendChild(style);
    }
    
    document.body.appendChild(tooltip);
    
    // Auto-remove after 10 seconds
    setTimeout(() => {
      this.hideProactiveSuggestionTooltip();
    }, 10000);
  }
  
  /**
   * Hides the proactive suggestion tooltip if visible.
   */
  hideProactiveSuggestionTooltip() {
    const existing = document.getElementById("proactive-suggestion-tooltip");
    if (existing) {
      existing.remove();
    }
  }
  
  /**
   * Formats a canvas block name for display.
   * @param {string} blockName - The raw block name (e.g., "customer_segments").
   * @returns {string} Formatted name (e.g., "Customer Segments").
   */
  formatBlockName(blockName) {
    if (!blockName) return "";
    return blockName
      .split("_")
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  }

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
