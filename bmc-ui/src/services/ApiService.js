class ApiService {
  constructor() {
    console.log("=== API SERVICE INIT DEBUG ===");

    // Check if NODE_ENV is defined (webpack defines it) - default to "production" for built apps
    const nodeEnv =
      (typeof process !== "undefined" && process.env && process.env.NODE_ENV) ||
      (typeof global !== "undefined" &&
        global.process &&
        global.process.env &&
        global.process.env.NODE_ENV) ||
      "production"; // Changed default from "development" to "production"
    console.log("NODE_ENV:", nodeEnv);

    const isProd = nodeEnv === "production";
    console.log("Is production build:", isProd);

    // First priority: If API_URL is explicitly provided via webpack env, use it
    if (typeof API_URL !== "undefined" && API_URL) {
      this.apiUrl = API_URL;
      console.log("Using API_URL from build environment:", API_URL);
      console.log("=== API SERVICE INIT COMPLETE ===");
      console.log("Final API URL:", this.apiUrl);
      return;
    }

    console.log("No explicit API_URL found, using hostname detection");
    console.log("Protocol:", window.location.protocol);
    console.log("Hostname:", window.location.hostname);
    console.log("Port:", window.location.port);

    // Development/localhost check - only for actual development environments
    if (
      window.location.hostname === "localhost" ||
      window.location.hostname === "127.0.0.1" ||
      window.location.hostname === "0.0.0.0"
    ) {
      console.log("Development localhost mode - using localhost:8001");
      this.apiUrl = "http://localhost:8001";
    } else {
      console.log("Production mode detected");

      // Detect Cloud Run service and route to correct API service
      const protocol = window.location.protocol;
      const hostname = window.location.hostname;

      if (hostname.includes("bmc-ui-")) {
        // We're on the UI service, switch to API service
        const apiHostname = hostname.replace(
          "bmc-ui-",
          "bmc-api-"
        );
        this.apiUrl = `${protocol}//${apiHostname}`;
        console.log("Detected UI service, using API service URL:", this.apiUrl);
      } else if (hostname.includes("bmc-api-")) {
        // Already on API service
        console.log("Already on API service hostname:", hostname);
        this.apiUrl = `${protocol}//${hostname}`;
      } else if (hostname.includes("philoagents-ui-")) {
        // Legacy support: We're on the old UI service, switch to old API service
        const apiHostname = hostname.replace(
          "philoagents-ui-",
          "philoagents-api-"
        );
        this.apiUrl = `${protocol}//${apiHostname}`;
        console.log("Detected legacy UI service, using legacy API service URL:", this.apiUrl);
      } else if (hostname.includes("philoagents-api-")) {
        // Already on legacy API service
        console.log("Already on legacy API service hostname:", hostname);
        this.apiUrl = `${protocol}//${hostname}`;
      } else {
        // Fallback for other production environments
        console.log("Unknown production hostname, using as-is:", hostname);
        this.apiUrl = `${protocol}//${hostname}`;
      }
    }

    // Fallback if somehow still undefined
    if (!this.apiUrl) {
      console.warn("API URL is undefined, using fallback!");
      this.apiUrl = "http://localhost:8001";
      console.log("Fallback API URL:", this.apiUrl);
    }

    console.log("=== API SERVICE INIT COMPLETE ===");
    console.log("Final API URL:", this.apiUrl);
  }

  async request(endpoint, method, data) {
    const url = `${this.apiUrl}${endpoint}`;
    console.log("Making request to:", url);
    const options = {
      method,
      headers: {
        "Content-Type": "application/json",
      },
      body: data ? JSON.stringify(data) : undefined,
    };

    const response = await fetch(url, options);

    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }

    return response.json();
  }

  async sendBusinessMessage(expert, message, userToken) {
    try {
      console.log("Sending business message:", { expert, message, userToken });

      const payload = {
        message,
        expert_id: expert.id,
        user_token: userToken,
      };

      // Check for business-specific image using the user token for isolation
      const imageKey = `tempBusinessImage_${userToken}`;
      const imageNameKey = `tempBusinessImageName_${userToken}`;
      const tempImage = window[imageKey];
      const tempImageName = window[imageNameKey];
      if (tempImage) {
        console.log(`SECURE: Found business-specific image for ${imageKey}`);
        console.log("SECURE: Image string length:", tempImage.length);
        console.log("SECURE: Image name:", tempImageName);
        console.log("SECURE: First 50 chars:", tempImage.substring(0, 50));

        payload.image_base64 = tempImage;
        payload.image_name = tempImageName;

        console.log(
          "SECURE: Business-specific image attached to payload (persisted for session)"
        );
      } else {
        console.log(`SECURE: No business-specific image found for ${imageKey}`);
      }

      // Check for business-specific PDF using the user token for isolation
      const pdfKey = `tempBusinessPdf_${userToken}`;
      const pdfNameKey = `tempBusinessPdfName_${userToken}`;
      const tempPdf = window[pdfKey];
      const tempPdfName = window[pdfNameKey];
      if (tempPdf) {
        console.log(`SECURE: Found business-specific PDF for ${pdfKey}`);
        console.log("SECURE: PDF string length:", tempPdf.length);
        console.log("SECURE: PDF name:", tempPdfName);

        payload.pdf_base64 = tempPdf;
        payload.pdf_name = tempPdfName;

        console.log(
          "SECURE: Business-specific PDF attached to payload (persisted for session)"
        );
      } else {
        console.log(`SECURE: No business-specific PDF found for ${pdfKey}`);
      }

      const data = await this.request("/chat/business", "POST", payload);
      return data.response;
    } catch (error) {
      console.error("Error sending business message to API:", error);
      console.error("Error details:", error.message, error.stack);
      return this.getFallbackResponse(expert);
    }
  }

  /**
   * Streams a business message response.
   * @param {Object} expert - The expert object.
   * @param {string} message - The user's message.
   * @param {string} userToken - The user's token.
   * @param {Function} onChunk - Callback for each text chunk received.
   * @param {Function} [onProactiveSuggestion] - Optional callback for proactive suggestions.
   * @returns {Promise<void>}
   */
  async streamBusinessMessage(expert, message, userToken, onChunk, onProactiveSuggestion = null) {
    try {
      console.log("Streaming business message:", { expert, message, userToken });

      const payload = {
        message,
        expert_id: expert.id,
        user_token: userToken,
      };

      // Check for business-specific image using the user token for isolation
      const imageKey = `tempBusinessImage_${userToken}`;
      const imageNameKey = `tempBusinessImageName_${userToken}`;
      const tempImage = window[imageKey];
      const tempImageName = window[imageNameKey];
      if (tempImage) {
        payload.image_base64 = tempImage;
        payload.image_name = tempImageName;
      }

      // Check for business-specific PDF using the user token for isolation
      const pdfKey = `tempBusinessPdf_${userToken}`;
      const pdfNameKey = `tempBusinessPdfName_${userToken}`;
      const tempPdf = window[pdfKey];
      const tempPdfName = window[pdfNameKey];
      if (tempPdf) {
        payload.pdf_base64 = tempPdf;
        payload.pdf_name = tempPdfName;
      }

      const response = await fetch(`${this.apiUrl}/chat/business/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status} ${response.statusText}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder("utf-8");
      
      // Buffer to accumulate chunks in case marker spans multiple chunks
      let buffer = "";
      const PROACTIVE_MARKER_START = "[PROACTIVE_SUGGESTION]";
      const PROACTIVE_MARKER_END = "[/PROACTIVE_SUGGESTION]";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        buffer += chunk;
        
        // Check if we have a complete proactive suggestion marker
        const markerStart = buffer.indexOf(PROACTIVE_MARKER_START);
        
        if (markerStart !== -1) {
          const markerEnd = buffer.indexOf(PROACTIVE_MARKER_END);
          
          if (markerEnd !== -1) {
            // We have a complete marker - extract and process
            const beforeMarker = buffer.substring(0, markerStart);
            const suggestionContent = buffer.substring(
              markerStart + PROACTIVE_MARKER_START.length, 
              markerEnd
            );
            
            // Send any text before the marker
            if (beforeMarker.trim()) {
              onChunk(beforeMarker);
            }
            
            // Parse the suggestion (format: "suggestion text|target_block")
            if (suggestionContent && onProactiveSuggestion) {
              const [suggestion, targetBlock] = suggestionContent.split("|");
              onProactiveSuggestion({
                suggestion: suggestion.trim(),
                targetBlock: targetBlock ? targetBlock.trim() : null
              });
            }
            
            // Clear the buffer after processing the marker
            buffer = buffer.substring(markerEnd + PROACTIVE_MARKER_END.length);
          }
          // If marker started but not ended, keep buffering
        } else {
          // No marker found, safe to send the buffered chunk
          if (buffer) {
            onChunk(buffer);
            buffer = "";
          }
        }
      }
      
      // Send any remaining buffer content
      if (buffer.trim()) {
        onChunk(buffer);
      }

    } catch (error) {
      console.error("Error streaming business message:", error);
      console.error("Error details:", error.message, error.stack);
      onChunk(this.getFallbackResponse(expert));
    }
  }

  async sendMessage(philosopher, message) {
    try {
      const data = await this.request("/chat", "POST", {
        message,
        philosopher_id: philosopher.id,
      });

      return data.response;
    } catch (error) {
      console.error("Error sending message to API:", error);
      return this.getFallbackResponse(philosopher);
    }
  }

  async validateToken(token) {
    try {
      const url = `${
        this.apiUrl
      }/business/tokens/validate?token=${encodeURIComponent(token)}`;
      const response = await fetch(url, {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error("Failed to validate token");
      }

      return await response.json();
    } catch (error) {
      console.error("Error validating token:", error);
      return { valid: false };
    }
  }

  async getBusinessExperts() {
    try {
      const data = await this.request("/business/experts", "GET");
      return data.experts;
    } catch (error) {
      console.error("Error fetching business experts:", error);
      return [];
    }
  }

  getFallbackResponse(character) {
    const type = character.domain ? "business expert" : "philosopher";
    return `I'm sorry, ${
      character.name || `the ${type}`
    } is unavailable at the moment. Please try again later.`;
  }

  async resetMemory(token) {
    try {
      const response = await fetch(`${this.apiUrl}/business/user/${token}/memory`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        throw new Error("Failed to reset memory");
      }

      return await response.json();
    } catch (error) {
      console.error("Error resetting memory:", error);
      throw error;
    }
  }

  // --- NEW CRUD FUNCTIONS ---

  /**
   * Fetches all business user profiles from the server.
   * @param {string} [adminToken] - Optional admin token for accessing all users.
   * @returns {Promise<Array<Object>>} A list of user profiles.
   */
  async getAllBusinessUsers(adminToken) {
    try {
      console.log("=== getAllBusinessUsers DEBUG ===");
      console.log("API URL being used:", this.apiUrl);

      let url = `${this.apiUrl}/business/users`;
      if (adminToken) {
        url = `${
          this.apiUrl
        }/admin/business/users?admin_token=${encodeURIComponent(adminToken)}`;
      }

      console.log("Full URL:", url);

      const response = await fetch(url, {
        method: "GET",
      });

      console.log("Response status:", response.status);
      console.log("Response ok:", response.ok);

      if (!response.ok) {
        const errorData = await response.json();
        console.error("Error response data:", errorData);
        throw new Error(errorData.detail || "Failed to fetch users");
      }

      const data = await response.json();
      console.log("Users data received:", data);
      return data;
    } catch (error) {
      console.error("Error fetching all business users:", error);
      throw error;
    }
  }

  /**
   * Fetches a single business user profile by token.
   * @param {string} token - The unique token of the user to fetch.
   * @returns {Promise<Object>} The user profile.
   */
  async getBusinessUser(token) {
    try {
      const response = await fetch(`${this.apiUrl}/business/user/${token}`, {
        method: "GET",
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to fetch user");
      }
      return await response.json();
    } catch (error) {
      console.error("Error fetching business user:", error);
      throw error;
    }
  }

  /**
   * Creates a new business user profile.
   * @param {Object} userData - The user profile object matching the BusinessUser model.
   * @returns {Promise<Object>} The server response.
   */
  async createBusinessUser(userData) {
    try {
      const response = await fetch(`${this.apiUrl}/business/user`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(userData),
      });
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to create user");
      }
      return await response.json();
    } catch (error) {
      console.error("Error creating business user:", error);
      throw error;
    }
  }

  /**
   * Updates an existing business user profile.
   * @param {string} token - The unique token of the user to update.
   * @param {Object} userData - The full, updated user profile object.
   * @returns {Promise<Object>} The server response.
   */
  async updateBusinessUser(token, userData) {
    try {
      const response = await fetch(`${this.apiUrl}/business/user/${token}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(userData),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to update user");
      }
      return await response.json();
    } catch (error) {
      console.error("Error updating business user:", error);
      throw error;
    }
  }

  /**
   * Deletes a business user profile.
   * @param {string} token - The unique token of the user to delete.
   * @returns {Promise<Object>} The server response.
   */
  async deleteBusinessUser(token) {
    try {
      const response = await fetch(`${this.apiUrl}/business/user/${token}`, {
        method: "DELETE",
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to delete user");
      }
      return await response.json();
    } catch (error) {
      console.error("Error deleting business user:", error);
      throw error;
    }
  }

  /**
   * Downloads the Business Model Canvas as a PDF file.
   * @param {string} token - The unique token of the user.
   * @returns {Promise<void>}
   */
  async downloadBMCPdf(token) {
    try {
      console.log("Downloading BMC PDF for token:", token);
      
      const response = await fetch(`${this.apiUrl}/business/user/${token}/export-pdf`, {
        method: "GET",
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to generate PDF");
      }

      // Get the blob from the response
      const blob = await response.blob();
      
      // Create a download link and trigger it
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      
      // Try to get filename from Content-Disposition header, fallback to default
      const contentDisposition = response.headers.get("Content-Disposition");
      let filename = "business-model-canvas.pdf";
      if (contentDisposition) {
        const match = contentDisposition.match(/filename="?(.+?)"?$/);
        if (match) {
          filename = match[1];
        }
      }
      
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      window.URL.revokeObjectURL(url);
      
      console.log("PDF download triggered successfully");
    } catch (error) {
      console.error("Error downloading BMC PDF:", error);
      throw error;
    }
  }

  // --- PROACTIVE SUGGESTION ACTIONS ---

  /**
   * Accept a proactive suggestion.
   * Removes from pending_topics and adds to the target canvas block.
   * @param {string} userToken - The user's token.
   * @param {string} suggestion - The suggestion text.
   * @param {string} targetBlock - The canvas block to add the suggestion to.
   * @returns {Promise<Object>} The server response.
   */
  async acceptSuggestion(userToken, suggestion, targetBlock) {
    try {
      const response = await fetch(
        `${this.apiUrl}/business/user/${userToken}/suggestion/accept`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            suggestion: suggestion,
            target_block: targetBlock,
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to accept suggestion");
      }

      return await response.json();
    } catch (error) {
      console.error("Error accepting suggestion:", error);
      throw error;
    }
  }

  /**
   * Dismiss a proactive suggestion.
   * Removes from pending_topics without adding to canvas.
   * @param {string} userToken - The user's token.
   * @param {string} suggestion - The suggestion text.
   * @returns {Promise<Object>} The server response.
   */
  async dismissSuggestion(userToken, suggestion) {
    try {
      const response = await fetch(
        `${this.apiUrl}/business/user/${userToken}/suggestion/dismiss`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            suggestion: suggestion,
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to dismiss suggestion");
      }

      return await response.json();
    } catch (error) {
      console.error("Error dismissing suggestion:", error);
      throw error;
    }
  }
}

const apiServiceInstance = new ApiService();
export default apiServiceInstance;
export { ApiService };
