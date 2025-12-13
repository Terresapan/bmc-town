import { Scene } from "phaser";
import ApiService from "../services/ApiService";

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

    const panel = this.add.graphics();
    panel.fillStyle(0xffffff, 1);
    panel.fillRoundedRect(centerX - 200, centerY - 150, 400, 300, 20);
    panel.lineStyle(4, 0x000000, 1);
    panel.strokeRoundedRect(centerX - 200, centerY - 150, 400, 300, 20);

    this.add
      .text(centerX, centerY - 120, "GAME PAUSED", {
        fontSize: "28px",
        fontFamily: "Arial",
        color: "#000000",
        fontStyle: "bold",
      })
      .setOrigin(0.5);

    const buttonY = centerY - 50;
    const buttonSpacing = 70;

    this.createButton(centerX, buttonY, "Resume Game", () => {
      this.resumeGame();
    });

    this.createButton(centerX, buttonY + buttonSpacing, "Main Menu", () => {
      this.returnToMainMenu();
    });

    this.createButton(
      centerX,
      buttonY + buttonSpacing * 2,
      "Reset Game",
      () => {
        this.resetGame();
      }
    );

    this.input.keyboard.on("keydown-ESC", () => {
      this.resumeGame();
    });

    // Generate gradient texture for buttons
    this.createGradientTexture("btn-gradient-pause", 250, 50, 15);
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

  createButton(x, y, text, callback) {
    const buttonWidth = 250;
    const buttonHeight = 50;
    const cornerRadius = 15;

    const shadow = this.add.graphics();
    shadow.fillStyle(0x000000, 0.4);
    shadow.fillRoundedRect(
      x - buttonWidth / 2 + 5,
      y - buttonHeight / 2 + 5,
      buttonWidth,
      buttonHeight,
      cornerRadius
    );

    const button = this.add.graphics();
    button.fillStyle(0xd946ef, 1); // fuchsia-500
    button.lineStyle(2, 0xd946ef, 1);
    button.fillRoundedRect(
      x - buttonWidth / 2,
      y - buttonHeight / 2,
      buttonWidth,
      buttonHeight,
      cornerRadius
    );
    button.strokeRoundedRect(
      x - buttonWidth / 2,
      y - buttonHeight / 2,
      buttonWidth,
      buttonHeight,
      cornerRadius
    );

    // Gradient sprite for hover (initially hidden)
    const buttonGradient = this.add
      .image(x, y, "btn-gradient-pause")
      .setOrigin(0.5)
      .setVisible(false);

    button.setInteractive(
      new Phaser.Geom.Rectangle(
        x - buttonWidth / 2,
        y - buttonHeight / 2,
        buttonWidth,
        buttonHeight
      ),
      Phaser.Geom.Rectangle.Contains
    );

    const buttonText = this.add
      .text(x, y, text, {
        fontSize: "22px",
        fontFamily: "Arial",
        color: "#FFFFFF",
        fontStyle: "bold",
      })
      .setOrigin(0.5);

    button.on("pointerover", () => {
      buttonGradient.setVisible(true);
      buttonText.y -= 2;
      buttonGradient.y -= 2;
    });

    button.on("pointerout", () => {
      buttonGradient.setVisible(false);
      buttonText.y = y;
      buttonGradient.y = y;
      // Reset base color if needed, though we operate via overlay visibility now. 
      // Ensuring consistency in case we modify implementation later.
      button.clear();
      button.fillStyle(0xd946ef, 1);
      button.lineStyle(2, 0xd946ef, 1);
      button.fillRoundedRect(
        x - buttonWidth / 2,
        y - buttonHeight / 2,
        buttonWidth,
        buttonHeight,
        cornerRadius
      );
      button.strokeRoundedRect(
        x - buttonWidth / 2,
        y - buttonHeight / 2,
        buttonWidth,
        buttonHeight,
        cornerRadius
      );
    });

    button.on("pointerdown", callback);

    return { button, shadow, text: buttonText };
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

    if (!confirm("Are you sure you want to RESET THE GAME?\n\nThis will wipe all shared memory and insights learned by the agents. Your profile metadata will remain, but the Canvas will be cleared.")) {
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
}
