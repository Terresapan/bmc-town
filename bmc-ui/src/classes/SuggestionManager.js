import ApiService from "../services/ApiService";

/**
 * SuggestionManager - Manages proactive suggestion state and UI
 * 
 * Implements the "Collapse-to-Badge" pattern:
 * 1. New suggestion shows as popup with Accept/Dismiss buttons
 * 2. If ignored for 30s OR new suggestion arrives, collapses to badge
 * 3. Badge click opens inbox panel with all queued suggestions
 */
class SuggestionManager {
  constructor(userToken) {
    this.userToken = userToken;
    this.suggestions = [];      // Queue of pending suggestions
    this.activePopup = null;    // Currently displayed popup element
    this.popupTimeout = null;   // 30s timeout reference
    this.badgeElement = null;   // Persistent badge element
    this.inboxElement = null;   // Inbox panel element
    
    this.initStyles();
    this.initBadge();
  }

  /**
   * Initialize the CSS styles for all suggestion UI components
   */
  initStyles() {
    if (document.getElementById("suggestion-manager-styles")) return;
    
    const style = document.createElement("style");
    style.id = "suggestion-manager-styles";
    style.textContent = `
      /* Popup Tooltip */
      .proactive-tooltip {
        position: fixed;
        top: 20px;
        right: 20px;
        max-width: 380px;
        background: linear-gradient(135deg, rgba(45, 55, 72, 0.98) 0%, rgba(26, 32, 44, 0.98) 100%);
        border: 1px solid rgba(99, 179, 237, 0.4);
        border-radius: 12px;
        padding: 16px 20px;
        display: flex;
        flex-direction: column;
        gap: 12px;
        box-shadow: 0 10px 40px rgba(0, 0, 0, 0.4), 0 0 20px rgba(99, 179, 237, 0.15);
        z-index: 10000;
        animation: slideInRight 0.4s ease-out;
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
      }
      
      @keyframes slideInRight {
        from { transform: translateX(100px); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
      }
      
      @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100px); opacity: 0; }
      }
      
      .proactive-tooltip-header {
        display: flex;
        align-items: flex-start;
        gap: 12px;
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
        position: absolute;
        top: 12px;
        right: 12px;
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
      
      /* Action Buttons */
      .proactive-tooltip-actions {
        display: flex;
        gap: 10px;
        margin-top: 12px;
      }
      
      .action-accept, .action-dismiss {
        flex: 1;
        padding: 8px 16px;
        border: none;
        border-radius: 6px;
        font-size: 13px;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
      }
      
      .action-accept {
        background: linear-gradient(135deg, #48bb78 0%, #38a169 100%);
        color: white;
      }
      
      .action-accept:hover {
        background: linear-gradient(135deg, #68d391 0%, #48bb78 100%);
        transform: translateY(-1px);
      }
      
      .action-dismiss {
        background: rgba(255, 255, 255, 0.1);
        color: rgba(255, 255, 255, 0.8);
        border: 1px solid rgba(255, 255, 255, 0.2);
      }
      
      .action-dismiss:hover {
        background: rgba(255, 255, 255, 0.15);
        color: white;
      }
      
      /* Badge */
      .suggestion-badge {
        position: fixed;
        top: 20px;
        right: 20px;
        background: linear-gradient(135deg, rgba(99, 179, 237, 0.9) 0%, rgba(66, 153, 225, 0.9) 100%);
        border-radius: 50px;
        padding: 10px 16px;
        display: flex;
        align-items: center;
        gap: 8px;
        cursor: pointer;
        z-index: 9999;
        box-shadow: 0 4px 15px rgba(66, 153, 225, 0.4);
        transition: all 0.3s ease;
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
      }
      
      .suggestion-badge:hover {
        transform: scale(1.05);
        box-shadow: 0 6px 20px rgba(66, 153, 225, 0.5);
      }
      
      .suggestion-badge.hidden {
        display: none;
      }
      
      .badge-icon {
        font-size: 20px;
      }
      
      .badge-count {
        font-size: 14px;
        font-weight: 600;
        color: white;
      }
      
      /* Inbox Panel */
      .suggestion-inbox {
        position: fixed;
        top: 70px;
        right: 20px;
        width: 400px;
        max-height: 70vh;
        background: linear-gradient(135deg, rgba(45, 55, 72, 0.98) 0%, rgba(26, 32, 44, 0.98) 100%);
        border: 1px solid rgba(99, 179, 237, 0.3);
        border-radius: 12px;
        padding: 20px;
        z-index: 10001;
        box-shadow: 0 15px 50px rgba(0, 0, 0, 0.5);
        font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
        overflow-y: auto;
      }
      
      .suggestion-inbox.hidden {
        display: none;
      }
      
      .suggestion-inbox h3 {
        margin: 0 0 16px 0;
        font-size: 16px;
        color: white;
        display: flex;
        align-items: center;
        gap: 8px;
      }
      
      .suggestion-list {
        display: flex;
        flex-direction: column;
        gap: 12px;
      }
      
      .suggestion-item {
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 14px;
      }
      
      .suggestion-item-text {
        font-size: 14px;
        color: rgba(255, 255, 255, 0.9);
        line-height: 1.5;
        margin-bottom: 8px;
      }
      
      .suggestion-item-target {
        font-size: 12px;
        color: rgba(154, 230, 180, 0.8);
        margin-bottom: 12px;
      }
      
      .suggestion-item-actions {
        display: flex;
        gap: 8px;
      }
      
      .suggestion-item .action-accept,
      .suggestion-item .action-dismiss {
        padding: 6px 12px;
        font-size: 12px;
      }
      
      .inbox-close {
        width: 100%;
        margin-top: 16px;
        padding: 10px;
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 6px;
        color: white;
        font-size: 13px;
        cursor: pointer;
        transition: background 0.2s;
      }
      
      .inbox-close:hover {
        background: rgba(255, 255, 255, 0.15);
      }
      
      .inbox-empty {
        text-align: center;
        color: rgba(255, 255, 255, 0.5);
        padding: 20px;
        font-size: 14px;
      }
    `;
    document.head.appendChild(style);
  }

  /**
   * Initialize the persistent badge element
   */
  initBadge() {
    this.badgeElement = document.createElement("div");
    this.badgeElement.id = "suggestion-badge";
    this.badgeElement.className = "suggestion-badge hidden";
    this.badgeElement.innerHTML = `
      <span class="badge-icon">💡</span>
      <span class="badge-count">0</span>
    `;
    this.badgeElement.addEventListener("click", () => this.toggleInbox());
    document.body.appendChild(this.badgeElement);
  }

  /**
   * Add a new suggestion to the queue
   */
  addSuggestion(suggestion) {
    if (!suggestion || !suggestion.suggestion) return;
    
    // Add to queue
    this.suggestions.push({
      text: suggestion.suggestion,
      targetBlock: suggestion.targetBlock,
      timestamp: Date.now()
    });
    
    console.log("💡 SuggestionManager: Added suggestion, queue size:", this.suggestions.length);
    
    // If popup is active, collapse it and update badge
    if (this.activePopup) {
      this.collapsePopup();
    }
    
    // Show new popup
    this.showPopup(this.suggestions[this.suggestions.length - 1], this.suggestions.length - 1);
  }

  /**
   * Show the popup for a suggestion
   */
  showPopup(suggestion, index) {
    // Hide badge while popup is visible
    this.hideBadge();
    
    // Clear any existing timeout
    if (this.popupTimeout) {
      clearTimeout(this.popupTimeout);
    }
    
    // Remove existing popup
    this.hidePopup();
    
    // Create popup element
    const popup = document.createElement("div");
    popup.id = "proactive-suggestion-tooltip";
    popup.className = "proactive-tooltip";
    popup.innerHTML = `
      <button class="proactive-tooltip-close">×</button>
      <div class="proactive-tooltip-header">
        <div class="proactive-tooltip-icon">💡</div>
        <div class="proactive-tooltip-content">
          <div class="proactive-tooltip-label">Canvas Advisor</div>
          <div class="proactive-tooltip-text">${suggestion.text}</div>
          ${suggestion.targetBlock ? `<div class="proactive-tooltip-target">→ ${this.formatBlockName(suggestion.targetBlock)}</div>` : ""}
        </div>
      </div>
      <div class="proactive-tooltip-actions">
        <button class="action-accept">✓ Accept</button>
        <button class="action-dismiss">✗ Dismiss</button>
      </div>
    `;
    
    // Add event listeners
    popup.querySelector(".proactive-tooltip-close").addEventListener("click", () => {
      this.collapsePopup();
    });
    
    popup.querySelector(".action-accept").addEventListener("click", () => {
      this.acceptSuggestion(index);
    });
    
    popup.querySelector(".action-dismiss").addEventListener("click", () => {
      this.dismissSuggestion(index);
    });
    
    document.body.appendChild(popup);
    this.activePopup = popup;
    
    // Set 30s timeout to collapse
    this.popupTimeout = setTimeout(() => {
      this.collapsePopup();
    }, 30000);
  }

  /**
   * Hide the current popup without animation
   */
  hidePopup() {
    if (this.activePopup) {
      this.activePopup.remove();
      this.activePopup = null;
    }
  }

  /**
   * Collapse popup to badge with animation
   */
  collapsePopup() {
    if (this.popupTimeout) {
      clearTimeout(this.popupTimeout);
      this.popupTimeout = null;
    }
    
    if (this.activePopup) {
      this.activePopup.style.animation = "slideOutRight 0.3s ease-out forwards";
      setTimeout(() => {
        this.hidePopup();
        this.updateBadge();
      }, 300);
    } else {
      this.updateBadge();
    }
  }

  /**
   * Update badge visibility and count
   */
  updateBadge() {
    if (this.suggestions.length > 0) {
      this.badgeElement.querySelector(".badge-count").textContent = this.suggestions.length;
      this.badgeElement.classList.remove("hidden");
    } else {
      this.hideBadge();
    }
  }

  /**
   * Hide the badge
   */
  hideBadge() {
    this.badgeElement.classList.add("hidden");
  }

  /**
   * Toggle inbox panel visibility
   */
  toggleInbox() {
    if (this.inboxElement && !this.inboxElement.classList.contains("hidden")) {
      this.hideInbox();
    } else {
      this.showInbox();
    }
  }

  /**
   * Show the inbox panel
   */
  showInbox() {
    this.hideInbox(); // Remove any existing
    
    this.inboxElement = document.createElement("div");
    this.inboxElement.id = "suggestion-inbox";
    this.inboxElement.className = "suggestion-inbox";
    
    let listHTML = "";
    if (this.suggestions.length === 0) {
      listHTML = `<div class="inbox-empty">No pending suggestions</div>`;
    } else {
      listHTML = this.suggestions.map((s, i) => `
        <div class="suggestion-item" data-index="${i}">
          <div class="suggestion-item-text">${s.text}</div>
          ${s.targetBlock ? `<div class="suggestion-item-target">→ ${this.formatBlockName(s.targetBlock)}</div>` : ""}
          <div class="suggestion-item-actions">
            <button class="action-accept" data-index="${i}">✓ Accept</button>
            <button class="action-dismiss" data-index="${i}">✗ Dismiss</button>
          </div>
        </div>
      `).join("");
    }
    
    this.inboxElement.innerHTML = `
      <h3>💡 Canvas Advisor Suggestions</h3>
      <div class="suggestion-list">${listHTML}</div>
      <button class="inbox-close">Close</button>
    `;
    
    // Add event listeners
    this.inboxElement.querySelector(".inbox-close").addEventListener("click", () => {
      this.hideInbox();
    });
    
    this.inboxElement.querySelectorAll(".action-accept").forEach(btn => {
      btn.addEventListener("click", (e) => {
        const index = parseInt(e.target.dataset.index);
        this.acceptSuggestion(index);
      });
    });
    
    this.inboxElement.querySelectorAll(".action-dismiss").forEach(btn => {
      btn.addEventListener("click", (e) => {
        const index = parseInt(e.target.dataset.index);
        this.dismissSuggestion(index);
      });
    });
    
    document.body.appendChild(this.inboxElement);
  }

  /**
   * Hide the inbox panel
   */
  hideInbox() {
    if (this.inboxElement) {
      this.inboxElement.remove();
      this.inboxElement = null;
    }
  }

  /**
   * Accept a suggestion - calls API and removes from queue
   */
  async acceptSuggestion(index) {
    const suggestion = this.suggestions[index];
    if (!suggestion) return;
    
    try {
      await ApiService.acceptSuggestion(
        this.userToken,
        suggestion.text,
        suggestion.targetBlock
      );
      console.log("✓ Suggestion accepted:", suggestion.text);
    } catch (error) {
      console.error("Failed to accept suggestion:", error);
    }
    
    // Remove from queue
    this.suggestions.splice(index, 1);
    
    // Update UI
    this.hidePopup();
    this.updateBadge();
    
    // Refresh inbox if open
    if (this.inboxElement && !this.inboxElement.classList.contains("hidden")) {
      this.showInbox();
    }
  }

  /**
   * Dismiss a suggestion - calls API and removes from queue
   */
  async dismissSuggestion(index) {
    const suggestion = this.suggestions[index];
    if (!suggestion) return;
    
    try {
      await ApiService.dismissSuggestion(
        this.userToken,
        suggestion.text
      );
      console.log("✗ Suggestion dismissed:", suggestion.text);
    } catch (error) {
      console.error("Failed to dismiss suggestion:", error);
    }
    
    // Remove from queue
    this.suggestions.splice(index, 1);
    
    // Update UI
    this.hidePopup();
    this.updateBadge();
    
    // Refresh inbox if open
    if (this.inboxElement && !this.inboxElement.classList.contains("hidden")) {
      this.showInbox();
    }
  }

  /**
   * Format a canvas block name for display
   */
  formatBlockName(blockName) {
    if (!blockName) return "";
    return blockName
      .split("_")
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ");
  }

  /**
   * Cleanup - remove all UI elements
   */
  destroy() {
    this.hidePopup();
    this.hideInbox();
    if (this.badgeElement) {
      this.badgeElement.remove();
    }
    if (this.popupTimeout) {
      clearTimeout(this.popupTimeout);
    }
  }
}

export default SuggestionManager;
