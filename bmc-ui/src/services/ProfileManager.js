import apiService from "./ApiService.js";

class ProfileManager {
  constructor() {
    this.currentMode = "create";
    this.editToken = null;
    this.currentBusinessToken = null;
    this.currentBusinessRole = "user";
    this.currentUser = null; // Store full user object for merging
  }

  initialize() {
    console.log("Initializing ProfileManager...");
    this.setupFormHandlers();

    // Expose necessary functions globally for now to maintain compatibility
    // with any inline event handlers or external calls, though we aim to remove them.
    window.showCreateForm = () => this.showCreateForm();
    window.showEditForm = (token) => this.showEditForm(token);
    window.refreshBusinessDropdown = null; // Will be set by MainMenu
  }

  setupFormHandlers() {
    const form = document.getElementById("client-form");
    const formContainer = document.getElementById("client-form-container");
    const cancelBtn = document.getElementById("form-cancel-btn");
    const submitBtn = document.getElementById("form-submit-btn");
    const fileInput = document.getElementById("business_image");
    const pdfInput = document.getElementById("business_pdf");

    const stopAll = (e) => e.stopPropagation();

    if (formContainer) {
      ["click", "mousedown", "mouseup", "pointerdown", "pointerup"].forEach(
        (evt) => formContainer.addEventListener(evt, stopAll)
      );
    }

    if (form) {
      ["click", "mousedown", "mouseup", "pointerdown", "pointerup"].forEach(
        (evt) => form.addEventListener(evt, stopAll)
      );

      // File Inputs
      if (fileInput) {
        fileInput.addEventListener("change", (e) =>
          this.handleFileSelect(e, "image")
        );
        ["mousedown", "mouseup", "pointerdown", "pointerup"].forEach((evt) =>
          fileInput.addEventListener(evt, stopAll)
        );
      }

      if (pdfInput) {
        pdfInput.addEventListener("change", (e) =>
          this.handleFileSelect(e, "pdf")
        );
        ["mousedown", "mouseup", "pointerdown", "pointerup"].forEach((evt) =>
          pdfInput.addEventListener(evt, stopAll)
        );
      }

      // Submit
      if (submitBtn) {
        submitBtn.addEventListener("click", async (e) => {
          e.preventDefault();
          e.stopPropagation();
          await this.handleSubmit();
        });
        ["mousedown", "mouseup", "pointerdown", "pointerup"].forEach((evt) =>
          submitBtn.addEventListener(evt, (e) => e.stopPropagation())
        );
      }

      // Other inputs
      const inputs = form.querySelectorAll(
        "input:not(#business_image):not(#business_pdf), textarea, select, button:not(#form-submit-btn)"
      );
      inputs.forEach((input) => {
        ["click", "mousedown", "mouseup", "pointerdown", "pointerup"].forEach(
          (evt) => input.addEventListener(evt, stopAll)
        );
      });
    }

    if (cancelBtn) {
      cancelBtn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        this.hideForm();
      });
    }
  }

  showCreateForm() {
    this.clearAllBusinessFiles();
    this.currentMode = "create";
    this.currentUser = null;

    document.getElementById("form-title").innerText =
      "Create New Client Profile";
    document.getElementById("form-submit-btn").innerText = "Create Profile";
    document.getElementById("client-form").reset();

    const tokenInput = document.getElementById("token");
    const tokenLabel = document.querySelector('label[for="token"]');
    if (tokenInput) {
      tokenInput.style.display = "none";
      tokenInput.required = false;
      tokenInput.value = "SYSTEM_GENERATED";
    }
    if (tokenLabel) tokenLabel.style.display = "none";

    document.getElementById("client-form-container").style.display = "flex";
  }

  async showEditForm(token) {
    this.currentMode = "edit";
    this.editToken = token;

    document.getElementById("form-title").innerText = "Edit Client Profile";
    document.getElementById("form-submit-btn").innerText = "Update Profile";

    const tokenInput = document.getElementById("token");
    const tokenLabel = document.querySelector('label[for="token"]');
    if (tokenInput) {
      tokenInput.style.display = "block";
      tokenInput.readOnly = true;
      tokenInput.disabled = true;
      tokenInput.style.backgroundColor = "rgba(255, 255, 255, 0.05)";
      tokenInput.value = token;
    }
    if (tokenLabel) tokenLabel.style.display = "block";

    document.getElementById("client-form-container").style.display = "flex";

    try {
      const user = await apiService.getBusinessUser(token);
      this.currentUser = user; // Store for merging logic

      if (user) {
        document.getElementById("owner_name").value = user.owner_name || "";
        document.getElementById("business_name").value =
          user.business_name || "";
        document.getElementById("sector").value = user.sector || "";
        document.getElementById("challenges").value =
          (user.challenges || []).join(", ") || "";
        document.getElementById("goals").value =
          (user.goals || []).join(", ") || "";
        // Note: Memory fields (constraints, preferences, pending_topics)
        // are now edited in the Canvas Preview modal
      }
    } catch (error) {
      console.error("Error fetching user details:", error);
      alert("Error fetching user details");
      this.hideForm();
    }
  }

  hideForm() {
    const formContainer = document.getElementById("client-form-container");
    if (formContainer) {
      formContainer.style.display = "none";
    }
  }

  async handleFileSelect(event, type) {
    const fileInput = event.target;
    if (fileInput.files.length > 0) {
      const file = fileInput.files[0];
      if (file.size > 5 * 1024 * 1024) {
        alert(`${type.toUpperCase()} size must be less than 5MB`);
        fileInput.value = "";
        return;
      }

      try {
        const base64 = await this.readFileAsBase64(file);

        if (type === "image") {
          // Use global variable for now as the game scene expects it there
          // TODO: Refactor Game.js to not rely on window globals for this
          window.tempBusinessImage = base64;
          window.tempBusinessImageName = file.name;

          // Also store with token if available (for security/isolation)
          const token = this.getCurrentBusinessToken();
          if (token) {
            window[`tempBusinessImage_${token}`] = base64;
            window[`tempBusinessImageName_${token}`] = file.name;
          }
          alert("Image Ready!");
        } else if (type === "pdf") {
          window.tempBusinessPdf = base64;
          window.tempBusinessPdfName = file.name;

          const token = this.getCurrentBusinessToken();
          if (token) {
            window[`tempBusinessPdf_${token}`] = base64;
            window[`tempBusinessPdfName_${token}`] = file.name;
          }
          alert("PDF Ready!");
        }
      } catch (err) {
        console.error(`Error processing ${type}:`, err);
        alert(`Failed to process ${type}.`);
      }
    }
  }

  async handleSubmit() {
    const formData = {
      owner_name: document.getElementById("owner_name").value.trim(),
      business_name: document.getElementById("business_name").value.trim(),
      sector: document.getElementById("sector").value.trim(),
      challenges: document
        .getElementById("challenges")
        .value.split(",")
        .map((s) => s.trim())
        .filter((s) => s),
      goals: document
        .getElementById("goals")
        .value.split(",")
        .map((s) => s.trim())
        .filter((s) => s),
    };

    // Note: Memory fields (constraints, preferences, pending_topics) are now edited
    // in the Canvas Preview modal. On create, we start with empty memory.
    // On edit, we preserve the existing key_insights.

    if (!formData.owner_name || !formData.business_name) {
      alert("Please fill in all required fields (Owner Name, Business Name).");
      return;
    }

    try {
      if (this.currentMode === "create") {
        formData.token = this.generateSecureToken();
        formData.role = "user";
        // New user starts with empty memory
        formData.key_insights = {
            constraints: [],
            preferences: [],
            pending_topics: [],
            canvas_state: {} // Empty canvas
        };
        
        await apiService.createBusinessUser(formData);
        alert("Profile created successfully!");
        this.hideForm();
        document.getElementById("client-form").reset();
      } else if (this.currentMode === "edit" && this.editToken) {
        formData.token = this.editToken; // Ensure token is sent
        
        // Preserve existing key_insights from Canvas Preview
        formData.key_insights = (this.currentUser && this.currentUser.key_insights) || {
            canvas_state: {},
            constraints: [],
            preferences: [],
            pending_topics: []
        };

        await apiService.updateBusinessUser(this.editToken, formData);
        alert("Profile updated successfully!");
      }

      if (window.refreshBusinessDropdown) {
        window.refreshBusinessDropdown();
      }
    } catch (error) {
      console.error("Form submission failed:", error);
      alert("Failed to save profile: " + (error.message || "Unknown error"));
    }
  }

  generateSecureToken() {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(
      /[xy]/g,
      function (c) {
        const r = (Math.random() * 16) | 0;
        const v = c === "x" ? r : (r & 0x3) | 0x8;
        return v.toString(16);
      }
    );
  }

  getCurrentBusinessToken() {
    const tokenField = document.getElementById("token");
    if (
      tokenField &&
      tokenField.value.trim() &&
      tokenField.value !== "SYSTEM_GENERATED"
    ) {
      return tokenField.value.trim();
    }
    return this.editToken;
  }

  readFileAsBase64(file) {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const base64String = reader.result.split(",")[1];
        const cleanBase64 = base64String.replace(/[\n\r]/g, "");
        resolve(cleanBase64);
      };
      reader.onerror = (error) => reject(error);
      reader.readAsDataURL(file);
    });
  }

  clearAllBusinessFiles() {
    // Clear legacy variables
    window.tempBusinessImage = null;
    window.tempBusinessImageName = null;
    window.tempBusinessPdf = null;
    window.tempBusinessPdfName = null;

    // Clear all business-specific variables
    Object.keys(window).forEach((key) => {
      if (
        key.startsWith("tempBusinessImage_") ||
        key.startsWith("tempBusinessImageName_") ||
        key.startsWith("tempBusinessPdf_") ||
        key.startsWith("tempBusinessPdfName_")
      ) {
        window[key] = null;
      }
    });
  }
}

export default new ProfileManager();
