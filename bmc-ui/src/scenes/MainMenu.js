import { Scene } from "phaser";
import apiService from "../services/ApiService.js";
import { AdminInterface } from "../services/AdminInterface.js";
import profileManager from "../services/ProfileManager.js";
import { Dropdown } from "../classes/Dropdown.js";
import { InstructionsPanel } from "../classes/InstructionsPanel.js";

export class MainMenu extends Scene {
  constructor() {
    super("MainMenu");
    this.selectedBusinessIndex = 0;
    this.userToken = null;
    this.businesses = [];
    this.databaseUsers = [];
    this.dropdown = null;
    this.instructionsPanel = null;
  }

  init(data) {
    if (data.mode === "admin") {
      this.currentMode = "admin";
      this.adminInterface = data.adminInterface;
    } else if (data.mode === "user") {
      this.currentMode = "user";
      this.userToken = data.userToken;
    } else {
      this.currentMode = "initial";
    }
  }

  async create() {
    this.add.image(0, 0, "background").setOrigin(0.1, -0.05).setScale(0.9);

    const centerX = this.cameras.main.width / 2;
    const buttonSpacing = 65;

    this.createGradientTexture("btn-gradient-large", 300, 40, 20);
    this.createGradientTexture("btn-gradient-small", 120, 40, 10);

    this.instructionsPanel = new InstructionsPanel(this);

    // AUTO-LOGIN CHECK (Only run in 'initial' mode to prevent infinite loops)
    if (this.currentMode === "initial") {
        await this.checkAutoLogin();
        // If checkAutoLogin redirects (starts Game or restarts MainMenu), we stop here.
        // But checkAutoLogin is async. If it returns false (no login), we fall through.
    }

    if (this.currentMode === "admin") {
      this.createAdminDashboard(centerX, 480, buttonSpacing);
    } else if (this.currentMode === "user") {
      this.createUserDashboard(centerX, 480, buttonSpacing);
    } else {
      // Only show initial menu if we are still in 'initial' mode (auto-login failed or didn't run)
      this.createInitialMenu(centerX, 680, buttonSpacing);
    }

    this.setupKeyboardInput();

    window.refreshBusinessDropdown = () => {
      if (this.currentMode === "admin" && this.adminInterface) {
        this.loadUsersFromDatabase(this.adminInterface.adminToken);
      }
    };
  }

  async checkAutoLogin() {
      const autoEnter = localStorage.getItem("autoEnterGame") === "true";
      
      // 1. Check for User Token
      const storedUserToken = localStorage.getItem("userToken");
      if (storedUserToken) {
          try {
              const validation = await apiService.validateToken(storedUserToken);
              if (validation.valid) {
                  this.userToken = storedUserToken;
                  
                  if (autoEnter) {
                      console.log("Auto-entering game (User Mode)...");
                      localStorage.removeItem("autoEnterGame"); // Consume flag
                      this.registry.set("gameMode", "business");
                      this.registry.set("userToken", this.userToken);
                      this.scene.start("Game");
                      return;
                  }

                  // Otherwise show dashboard
                  this.scene.restart({ mode: "user", userToken: this.userToken });
                  return;
              } else {
                  localStorage.removeItem("userToken");
              }
          } catch (e) {
              console.error("User auto-login failed:", e);
          }
      }

      // 2. Check for Admin Token
      const storedAdminToken = localStorage.getItem("adminToken");
      if (storedAdminToken) {
          try {
              const adminInterface = new AdminInterface(apiService.apiUrl);
              // There isn't a direct 'validateToken' on AdminInterface that is public/static, 
              // but we can try to load users. If it works, token is valid.
              // Or better, assume valid and let the dashboard load fail if not.
              // Actually, AdminInterface has a token property.
              adminInterface.adminToken = storedAdminToken;
              
              // Verify by fetching users (lightweight auth check)
              await apiService.getAllBusinessUsers(storedAdminToken);
              
              // Auth success
              if (autoEnter) {
                  const selectedUser = localStorage.getItem("adminSelectedUserToken");
                  if (selectedUser) {
                      console.log("Auto-entering game (Admin Mode)...");
                      localStorage.removeItem("autoEnterGame");
                      this.registry.set("gameMode", "business");
                      this.registry.set("userToken", selectedUser);
                      this.scene.start("Game");
                      return;
                  }
              }

              this.scene.restart({ mode: "admin", adminInterface: adminInterface });
              return;

          } catch (e) {
              console.error("Admin auto-login failed:", e);
              localStorage.removeItem("adminToken");
          }
      }
  }

  createGradientTexture(key, w, h, r) {
    if (this.textures.exists(key)) {
      return;
    }
    const canvas = this.textures.createCanvas(key, w, h);
    const context = canvas.context;
    const grd = context.createLinearGradient(0, 0, w, 0);
    grd.addColorStop(0, "#d946ef");
    grd.addColorStop(0.5, "#a855f7");
    grd.addColorStop(1, "#6366f1");

    context.fillStyle = grd;
    context.beginPath();
    context.moveTo(r, 0);
    context.lineTo(w - r, 0);
    context.quadraticCurveTo(w, 0, w, r);
    context.lineTo(w, h - r);
    context.quadraticCurveTo(w, h, w - r, h);
    context.lineTo(r, h);
    context.quadraticCurveTo(0, h, 0, h - r);
    context.lineTo(0, r);
    context.quadraticCurveTo(0, 0, r, 0);
    context.closePath();
    context.fill();

    canvas.refresh();
  }

  createInitialMenu(centerX, startY, buttonSpacing) {
    this.add
      .text(centerX, startY - 35, "Select Access Mode:", {
        fontSize: "24px",
        fontFamily: "Arial",
        color: "#ffffff",
        stroke: "#000000",
        strokeThickness: 2,
      })
      .setOrigin(0.5);

    this.createButton(centerX - 180, startY + 20, "Admin Access", () =>
      this.handleAdminAccess()
    );
    this.createButton(centerX + 180, startY + 20, "User Access", () =>
      this.handleUserAccess()
    );
  }

  async createAdminDashboard(centerX, startY, buttonSpacing) {
    // Dropdown
    this.dropdown = new Dropdown(
      this,
      centerX,
      startY - 30,
      350,
      40,
      [],
      (index, item) => {
        this.selectedBusinessIndex = index;
      }
    );

    await this.loadUsersFromDatabase(this.adminInterface.adminToken);

    const firstLineY = startY + 40;
    const secondLineY = firstLineY + buttonSpacing;

    this.createButton(centerX - 180, firstLineY, "Enter Game", () =>
      this.validateAndEnterGame()
    );
    this.createButton(centerX + 180, firstLineY, "Instructions", () =>
      this.instructionsPanel.show()
    );

    this.createButton(centerX - 180, secondLineY, "Create Profile", () => {
      profileManager.showCreateForm();
    });
    this.createButton(centerX + 180, secondLineY, "Edit Profile", () =>
      this.showEditProfile()
    );

    this.createButton(centerX, secondLineY + buttonSpacing, "Logout", () => {
      this.adminInterface = null;
      localStorage.removeItem("adminToken");
      localStorage.removeItem("adminSelectedUserToken");
      this.scene.restart({ mode: "initial" });
    });
  }

  createUserDashboard(centerX, startY, buttonSpacing) {
    this.add
      .text(centerX, startY, `Token: ${this.userToken}`, {
        fontSize: "16px",
        color: "#ffffff",
        backgroundColor: "#333",
      })
      .setOrigin(0.5);

    const firstLineY = startY + 60;
    const secondLineY = firstLineY + buttonSpacing;

    this.createButton(centerX - 180, firstLineY, "Enter Game", () =>
      this.validateAndEnterGame()
    );
    this.createButton(centerX + 180, firstLineY, "Instructions", () =>
      this.instructionsPanel.show()
    );

    this.createButton(centerX - 180, secondLineY, "Edit Profile", () => {
      profileManager.showEditForm(this.userToken);
    });
    this.createButton(centerX + 180, secondLineY, "Back", () => {
      // Logout logic
      localStorage.removeItem("userToken");
      this.userToken = null;
      this.scene.restart({ mode: "initial" });
    });
  }

  async handleAdminAccess() {
    const adminInterface = new AdminInterface(apiService.apiUrl);
    const success = await adminInterface.login();

    if (success) {
      localStorage.setItem("adminToken", adminInterface.adminToken);
      this.showMessage("Admin Logged In!", "#00ff00");
      this.adminInterface = adminInterface;
      this.showAdminDashboard();
    }
  }

  async handleUserAccess() {
    const token = prompt("Enter your Business Token:");
    if (token && token.trim()) {
      const validation = await apiService.validateToken(token.trim());
      if (validation.valid) {
        this.userToken = token.trim();
        // Persist token
        localStorage.setItem("userToken", this.userToken);
        
        this.showMessage(
          `Welcome, ${validation.user.business_name}!`,
          "#00ff00"
        );
        this.showUserDashboard();
      } else {
        this.showMessage("Invalid Token", "#ff0000");
      }
    }
  }

  showAdminDashboard() {
    this.scene.restart({ mode: "admin", adminInterface: this.adminInterface });
  }

  showUserDashboard() {
    this.scene.restart({ mode: "user", userToken: this.userToken });
  }

  async loadUsersFromDatabase(adminToken = null) {
    try {
      this.databaseUsers = await apiService.getAllBusinessUsers(adminToken);

      if (this.databaseUsers && this.databaseUsers.length > 0) {
        this.businesses = this.databaseUsers.map((user) => user.business_name);
        if (this.dropdown) {
          this.dropdown.updateItems(this.businesses);
        }
        this.showMessage(
          `Loaded ${this.businesses.length} profiles.`,
          "#000000"
        );
      } else {
        this.businesses = [];
        if (this.dropdown) {
          this.dropdown.updateItems([]);
        }
      }
    } catch (error) {
      console.error("Error loading users:", error);
      this.businesses = [];
      if (this.dropdown) {
        this.dropdown.updateItems([]);
      }
      this.showMessage("Failed to load profiles.", "#ff0000");
    }
  }

  showEditProfile() {
    if (!this.databaseUsers || this.databaseUsers.length === 0) {
      this.showMessage(
        "No profiles to edit. Create a profile first.",
        "#ff0000"
      );
      return;
    }

    const selectedBusiness = this.businesses[this.selectedBusinessIndex];
    if (!selectedBusiness) {
      this.showMessage(
        "Please select a profile to edit from the dropdown.",
        "#ff0000"
      );
      return;
    }

    const user = this.databaseUsers.find(
      (u) => u.business_name === selectedBusiness
    );
    if (user && user.token) {
      profileManager.showEditForm(user.token);
    } else {
      this.showMessage("Selected profile not found in database.", "#ff0000");
    }
  }

  validateAndEnterGame() {
    if (this.currentMode === "user" && this.userToken) {
      this.registry.set("gameMode", "business");
      this.registry.set("userToken", this.userToken);
      this.scene.start("Game");
      return;
    }

    if (this.currentMode === "admin") {
      if (
        this.businesses &&
        this.businesses.length > 0 &&
        this.selectedBusinessIndex >= 0
      ) {
        const selectedBusiness = this.businesses[this.selectedBusinessIndex];
        const user = this.databaseUsers.find(
          (u) => u.business_name === selectedBusiness
        );

        if (user && user.token) {
          // Persist the selection so we can auto-enter after reset
          localStorage.setItem("adminSelectedUserToken", user.token);
          
          this.registry.set("gameMode", "business");
          this.registry.set("userToken", user.token);
          this.scene.start("Game");
          return;
        }
      }
      this.showMessage("Please select a profile.", "#ff0000");
    }
  }

  setupKeyboardInput() {
    this.input.keyboard.on("keydown", (event) => {
      if (event.key === "Enter") {
        this.validateAndEnterGame();
      }
    });
  }

  showMessage(text, color = "#ffffff") {
    if (this.messageText) {
      this.messageText.destroy();
    }

    const centerX = this.cameras.main.width / 2;
    this.messageText = this.add
      .text(centerX, 400, text, {
        fontSize: "18px",
        fontFamily: "Arial",
        color: color,
        stroke: "#000000",
        strokeThickness: 1,
      })
      .setOrigin(0.5);

    this.time.delayedCall(3000, () => {
      if (this.messageText) {
        this.messageText.destroy();
        this.messageText = null;
      }
    });
  }

  createButton(x, y, text, callback) {
    const buttonWidth = 300;
    const buttonHeight = 40;
    const cornerRadius = 20;

    const shadow = this.add.graphics();
    shadow.fillStyle(0x666666, 1);
    shadow.fillRoundedRect(
      x - buttonWidth / 2 + 4,
      y - buttonHeight / 2 + 4,
      buttonWidth,
      buttonHeight,
      cornerRadius
    );

    const button = this.add.graphics();
    button.fillStyle(0xffffff, 1);
    button.fillRoundedRect(
      x - buttonWidth / 2,
      y - buttonHeight / 2,
      buttonWidth,
      buttonHeight,
      cornerRadius
    );

    // Gradient sprite for hover (initially hidden)
    const buttonGradient = this.add
      .image(x, y, "btn-gradient-large")
      .setOrigin(0.5)
      .setVisible(false);

    const buttonText = this.add
      .text(x, y, text, {
        fontSize: "20px",
        fontFamily: "Arial",
        color: "#000000",
        fontStyle: "bold",
      })
      .setOrigin(0.5);

    const hitArea = this.add
      .rectangle(x, y, buttonWidth, buttonHeight, 0x000000, 0)
      .setInteractive();

    hitArea.on("pointerover", () => {
      buttonGradient.setVisible(true);
      buttonText.setStyle({ color: "#ffffff" });
      buttonText.y -= 2;
      buttonGradient.y -= 2;
    });

    hitArea.on("pointerout", () => {
      buttonGradient.setVisible(false);
      buttonText.setStyle({ color: "#000000" });
      buttonText.y = y;
      buttonGradient.y = y;
    });

    hitArea.on("pointerdown", callback);

    return { button, buttonGradient, shadow, text: buttonText, hitArea };
  }
}
