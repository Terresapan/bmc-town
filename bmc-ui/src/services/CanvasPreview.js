/**
 * CanvasPreview Service
 * 
 * Handles the Canvas Preview modal functionality:
 * - Fetch user's BMC data from API
 * - Display in editable form
 * - Save changes to database
 * - Trigger PDF download
 */

import ApiService from './ApiService';

class CanvasPreviewService {
  constructor() {
    this.container = null;
    this.modal = null;
    this.currentToken = null;
    this.currentUserData = null;
    this.onCloseCallback = null;
    this.initialized = false; // Prevent duplicate initialization
    
    // Bind methods
    this.show = this.show.bind(this);
    this.hide = this.hide.bind(this);
    this.save = this.save.bind(this);
    this.download = this.download.bind(this);
  }

  /**
   * Initialize the service by attaching event listeners
   */
  init() {
    // Prevent duplicate initialization
    if (this.initialized) {
      return;
    }
    
    this.container = document.getElementById('canvas-preview-container');
    this.modal = document.getElementById('canvas-preview-modal');
    
    if (!this.container || !this.modal) {
      console.error('CanvasPreview: Modal elements not found');
      return;
    }

    // Attach button handlers
    document.getElementById('preview-save-btn')?.addEventListener('click', this.save);
    document.getElementById('preview-download-btn')?.addEventListener('click', this.download);
    document.getElementById('preview-close-btn')?.addEventListener('click', this.hide);
    
    // Close on overlay click
    this.container.addEventListener('click', (e) => {
      if (e.target === this.container) {
        this.hide();
      }
    });

    // Prevent modal clicks from closing
    this.modal.addEventListener('click', (e) => e.stopPropagation());
    
    this.initialized = true;
  }

  /**
   * Show the canvas preview modal
   * @param {string} token - User token
   * @param {Function} onClose - Optional callback when modal closes
   */
  async show(token, onClose = null) {
    this.currentToken = token;
    this.onCloseCallback = onClose;

    try {
      // Fetch user data
      this.currentUserData = await ApiService.getBusinessUser(token);
      
      // Populate the form
      this.populateForm(this.currentUserData);
      
      // Show the modal
      this.container.style.display = 'flex';
      
    } catch (error) {
      console.error('CanvasPreview: Failed to load user data', error);
      alert('Failed to load canvas data. Please try again.');
    }
  }

  /**
   * Hide the modal
   */
  hide() {
    this.container.style.display = 'none';
    if (this.onCloseCallback) {
      this.onCloseCallback();
    }
  }

  /**
   * Populate form fields with user data
   */
  populateForm(userData) {
    const keyInsights = userData.key_insights || {};
    const canvasState = keyInsights.canvas_state || {};

    // BMC blocks - each is an array, display as newline-separated
    const bmcFields = [
      'key_partnerships',
      'key_activities', 
      'key_resources',
      'value_propositions',
      'customer_relationships',
      'channels',
      'customer_segments',
      'cost_structure',
      'revenue_streams'
    ];

    bmcFields.forEach(field => {
      const textarea = document.getElementById(`edit-${field}`);
      if (textarea) {
        const items = canvasState[field] || [];
        textarea.value = items.join('\n');
      }
    });

    // Extra insights
    const constraintsEl = document.getElementById('edit-constraints');
    if (constraintsEl) {
      constraintsEl.value = (keyInsights.constraints || []).join('\n');
    }

    const preferencesEl = document.getElementById('edit-preferences');
    if (preferencesEl) {
      preferencesEl.value = (keyInsights.preferences || []).join('\n');
    }

    const pendingEl = document.getElementById('edit-pending_topics');
    if (pendingEl) {
      pendingEl.value = (keyInsights.pending_topics || []).join('\n');
    }
  }

  /**
   * Collect form data into user object format
   */
  collectFormData() {
    const canvasState = {};
    
    const bmcFields = [
      'key_partnerships',
      'key_activities', 
      'key_resources',
      'value_propositions',
      'customer_relationships',
      'channels',
      'customer_segments',
      'cost_structure',
      'revenue_streams'
    ];

    bmcFields.forEach(field => {
      const textarea = document.getElementById(`edit-${field}`);
      if (textarea) {
        // Split by newlines, filter empty, trim whitespace
        canvasState[field] = textarea.value
          .split('\n')
          .map(s => s.trim())
          .filter(s => s.length > 0);
      }
    });

    // Extra insights
    const constraints = document.getElementById('edit-constraints')?.value
      .split('\n').map(s => s.trim()).filter(s => s.length > 0) || [];
    
    const preferences = document.getElementById('edit-preferences')?.value
      .split('\n').map(s => s.trim()).filter(s => s.length > 0) || [];
    
    const pending_topics = document.getElementById('edit-pending_topics')?.value
      .split('\n').map(s => s.trim()).filter(s => s.length > 0) || [];

    return {
      key_insights: {
        canvas_state: canvasState,
        constraints,
        preferences,
        pending_topics
      }
    };
  }

  /**
   * Save changes to database
   */
  async save() {
    const saveBtn = document.getElementById('preview-save-btn');
    const originalText = saveBtn.textContent;
    
    try {
      saveBtn.textContent = 'Saving...';
      saveBtn.disabled = true;

      // Collect form data
      const formData = this.collectFormData();
      
      // Merge with current user data
      const updatedUser = {
        ...this.currentUserData,
        key_insights: formData.key_insights
      };

      // Update via API
      await ApiService.updateBusinessUser(this.currentToken, updatedUser);
      
      // Update local cache
      this.currentUserData = updatedUser;
      
      saveBtn.textContent = '✓ Saved!';
      setTimeout(() => {
        saveBtn.textContent = originalText;
        saveBtn.disabled = false;
      }, 1500);

    } catch (error) {
      console.error('CanvasPreview: Save failed', error);
      saveBtn.textContent = '✗ Failed';
      setTimeout(() => {
        saveBtn.textContent = originalText;
        saveBtn.disabled = false;
      }, 1500);
      alert('Failed to save changes. Please try again.');
    }
  }

  /**
   * Download PDF (saves first, then downloads)
   */
  async download() {
    const downloadBtn = document.getElementById('preview-download-btn');
    const originalText = downloadBtn.textContent;

    try {
      downloadBtn.textContent = 'Saving & Downloading...';
      downloadBtn.disabled = true;

      // Save first to ensure PDF has latest data
      await this.save();
      
      // Small delay to ensure save completes
      await new Promise(resolve => setTimeout(resolve, 500));

      // Trigger PDF download
      await ApiService.downloadBMCPdf(this.currentToken);
      
      downloadBtn.textContent = '✓ Downloaded!';
      setTimeout(() => {
        downloadBtn.textContent = originalText;
        downloadBtn.disabled = false;
      }, 1500);

    } catch (error) {
      console.error('CanvasPreview: Download failed', error);
      downloadBtn.textContent = '✗ Failed';
      setTimeout(() => {
        downloadBtn.textContent = originalText;
        downloadBtn.disabled = false;
      }, 1500);
      alert('Failed to download PDF. Please try again.');
    }
  }
}

// Export singleton instance
const canvasPreview = new CanvasPreviewService();
export default canvasPreview;
export { CanvasPreviewService };
