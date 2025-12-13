// Admin interface for managing all business profiles
export class AdminInterface {
  constructor(apiUrl) {
    this.apiUrl = apiUrl;
    this.adminToken = null;
    this.businesses = [];
  }

  async login(providedPassword = null) {
    // 1. Get Password (if not provided)
    const password = providedPassword || prompt("Enter Admin Password:");
    if (!password) return false;

    if (password !== "agentgarden") {
        alert("Incorrect Password");
        return false;
    }

    // 2. Try using the password as the token first (Convenience)
    // If the user sets ADMIN_TOKEN="agentgarden" in .env, this allows single-step login.
    if (await this.validateToken(password)) {
        this.adminToken = password;
        return true;
    }

    // 3. If password is correct but not a valid token, prompt for the actual API Token
    const token = prompt("Password accepted. Please enter your Admin API Token:");
    if (!token) return false;

    if (await this.validateToken(token)) {
        this.adminToken = token;
        return true;
    } else {
        alert("Invalid Admin Token");
        return false;
    }
  }

  async validateToken(token) {
    try {
      const response = await fetch(`${this.apiUrl}/admin/business/users?admin_token=${encodeURIComponent(token)}`);
      if (response.ok) {
        this.businesses = await response.json();
        return true;
      }
      return false;
    } catch (error) {
      console.error("Token validation failed:", error);
      return false;
    }
  }
}
