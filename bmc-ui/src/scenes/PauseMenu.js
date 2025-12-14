import { Scene } from "phaser";
import ApiService from "../services/ApiService";
import canvasPreview from "../services/CanvasPreview";

export class PauseMenu extends Scene {
  constructor() {
    super("PauseMenu");
  }

  create() {
    const overlay = this.add.graphics();
    overlay.fillStyle(0x000000, 0.7);
    overlay.fillRect(0, 0, this.cameras.main.width, this.cameras.main.height);

    const centerX = this.cameras.main.width / 2;
    const centerY = this.cameras.main.height / 2;

    // Dark panel background (Lighter Gray-800: #1F2937 to be less harsh)
    const panel = this.add.graphics();
    panel.fillStyle(0x1F2937, 1);
    // Position panel slightly higher (-170 instead of -150) and taller (340 instead of 300)
    // to give breathing room at the bottom
    panel.fillRoundedRect(centerX - 160, centerY - 170, 320, 340, 16);
    panel.lineStyle(1, 0x4B5563, 1); // Gray-600 border
    panel.strokeRoundedRect(centerX - 160, centerY - 170, 320, 340, 16);

    // Gradient Text for Title (Shifted up slightly)
    const titleText = this.add
      .text(centerX, centerY - 120, "GAME PAUSED", {
        fontSize: "24px",
        fontFamily: "Arial",
        fontStyle: "bold",
        color: "#d946ef",
      })
      .setOrigin(0.5);

    // Apply gradient fill to text
    const gradient = titleText.context.createLinearGradient(0, 0, titleText.width, 0);
    gradient.addColorStop(0, "#d946ef");
    gradient.addColorStop(0.5, "#a855f7");
    gradient.addColorStop(1, "#6366f1");

    titleText.style.setFill(gradient);
    titleText.setText("GAME PAUSED");

    // Start buttons higher up (-55 instead of -45)
    const buttonY = centerY - 55;
    const buttonSpacing = 55;

    // Generate gradient texture for buttons
    this.createGradientTexture("btn-gradient-pause", 180, 36, 8);

    this.createButton(centerX, buttonY, "Resume Game", () => {
      this.resumeGame();
    });

    this.createButton(centerX, buttonY + buttonSpacing, "Main Menu", () => {
      this.returnToMainMenu();
    });

    this.createButton(
      centerX,
      buttonY + buttonSpacing * 2,
      "Export Canvas",
      () => {
        this.exportCanvas();
      }
    );

    this.createButton(
      centerX,
      buttonY + buttonSpacing * 3,
      "Reset Game",
      () => {
        this.resetGame();
      }
    );

    this.input.keyboard.on("keydown-ESC", () => {
      this.resumeGame();
    });
  }

  createGradientTexture(key, w, h, r) {
    if (this.textures.exists(key)) {
      this.textures.remove(key);
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

  createButton(x, y, text, callback) {
    const buttonWidth = 180;
    const buttonHeight = 36;
    const cornerRadius = 8;

    // Shadow
    const shadow = this.add.graphics();
    shadow.fillStyle(0x000000, 0.4);
    shadow.fillRoundedRect(
      x - buttonWidth / 2 + 2,
      y - buttonHeight / 2 + 2,
      buttonWidth,
      buttonHeight,
      cornerRadius
    );

    // Base Button (White)
    const button = this.add.graphics();
    button.fillStyle(0xffffff, 1);
    button.fillRoundedRect(
      x - buttonWidth / 2,
      y - buttonHeight / 2,
      buttonWidth,
      buttonHeight,
      cornerRadius
    );

    // Gradient sprite for hover - ensure correct depth
    const buttonGradient = this.add
      .image(x, y, "btn-gradient-pause")
      .setOrigin(0.5)
      .setVisible(false)
      .setDepth(10); 

    // Text - Topmost depth
    const buttonText = this.add
      .text(x, y, text, {
        fontSize: "16px",
        fontFamily: "Arial",
        color: "#000000",
        fontStyle: "bold",
      })
      .setOrigin(0.5)
      .setDepth(11);

    // Hit Zone
    const hitZone = this.add.zone(x, y, buttonWidth, buttonHeight)
      .setOrigin(0.5)
      .setInteractive({ useHandCursor: true });

    hitZone.on("pointerover", () => {
      buttonGradient.setVisible(true);
      buttonText.setStyle({ color: "#ffffff" });
      
      // Lift effect
      const lift = 1;
      buttonGradient.y = y - lift;
      buttonText.y = y - lift;
      // We don't move the white button background, the gradient covers it
    });

    hitZone.on("pointerout", () => {
      buttonGradient.setVisible(false);
      buttonText.setStyle({ color: "#000000" });
      
      // Reset position
      buttonGradient.y = y;
      buttonText.y = y;
    });

    hitZone.on("pointerdown", callback);

    return { button, shadow, text: buttonText, hitZone };
  }

  resumeGame() {
    this.scene.resume("Game");
    this.scene.stop();
  }

  returnToMainMenu() {
    this.scene.stop("Game");
    this.scene.start("MainMenu");
  }

  async resetGame() {
    const token = this.registry.get("userToken");
    
    if (!token) {
      console.error("No user token found, cannot reset memory.");
      alert("Error: No active user session found.");
      return;
    }

    if (!confirm("Are you sure you want to RESET THE GAME?\\n\\nThis will wipe all shared memory and insights learned by the agents. Your profile metadata will remain, but the Canvas will be cleared.")) {
        return;
    }

    try {
      await ApiService.resetMemory(token);
      alert("Memory wiped. Game resetting...");
      
      // Set flag to auto-enter game after reload
      localStorage.setItem("autoEnterGame", "true");
      
      window.location.reload();
    } catch (error) {
      console.error("Failed to reset game:", error);
      alert("Failed to reset game. Please try again.");
    }
  }

  async exportCanvas() {
    const token = this.registry.get("userToken");
    
    if (!token) {
      console.error("No user token found, cannot export canvas.");
      alert("Error: No active user session found.");
      return;
    }

    try {
      // Initialize canvas preview if not already done
      canvasPreview.init();
      
      // Show the preview modal (fetches data and displays it)
      await canvasPreview.show(token, () => {
        // Optional: callback when modal closes
        console.log("Canvas preview closed");
      });
      
    } catch (error) {
      console.error("Failed to show canvas preview:", error);
      alert("Failed to load canvas. Please try again.\\n\\n" + error.message);
    }
  }
}
