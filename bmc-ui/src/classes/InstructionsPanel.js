export class InstructionsPanel {
    constructor(scene) {
        this.scene = scene;
        this.elements = [];
    }

    show() {
        const width = this.scene.cameras.main.width;
        const height = this.scene.cameras.main.height;
        const centerX = width / 2;
        const centerY = height / 2;

        // Overlay
        const overlay = this.scene.add.graphics();
        overlay.fillStyle(0x000000, 0.7);
        overlay.fillRect(0, 0, width, height);
        overlay.setInteractive(new Phaser.Geom.Rectangle(0, 0, width, height), Phaser.Geom.Rectangle.Contains);
        overlay.on("pointerdown", () => this.hide());
        this.elements.push(overlay);

        // Panel
        const panel = this.scene.add.graphics();
        panel.fillStyle(0xffffff, 1);
        panel.fillRoundedRect(centerX - 200, centerY - 150, 400, 300, 20);
        panel.lineStyle(4, 0x000000, 1);
        panel.strokeRoundedRect(centerX - 200, centerY - 150, 400, 300, 20);
        this.elements.push(panel);

        // Title
        const title = this.scene.add.text(centerX, centerY - 110, "INSTRUCTIONS", {
            fontSize: "20px",
            fontFamily: "Arial",
            color: "#000000",
            fontStyle: "bold",
        }).setOrigin(0.5);
        this.elements.push(title);

        // Instructions Text
        const instructions = [
            "Arrow keys for moving",
            "SPACE for talking to business experts",
            "ESC for closing the dialogue",
        ];

        instructions.forEach((text, index) => {
            const instructionText = this.scene.add.text(centerX, centerY - 60 + index * 40, text, {
                fontSize: "18px",
                fontFamily: "Arial",
                color: "#333333",
            }).setOrigin(0.5);
            this.elements.push(instructionText);
        });

        // Close Button
        this.createCloseButton(centerX, centerY + 79);
    }

    createCloseButton(x, y) {
        const buttonWidth = 120;
        const buttonHeight = 40;

        const button = this.scene.add.image(x, y, "btn-gradient-small").setOrigin(0.5);
        
        const text = this.scene.add.text(x, y, "Close", {
            fontSize: "18px",
            fontFamily: "Arial",
            color: "#ffffff",
        }).setOrigin(0.5);

        const hitArea = this.scene.add.rectangle(x, y, buttonWidth, buttonHeight, 0x000000, 0).setInteractive();
        
        hitArea.on("pointerover", () => {
            button.setScale(1.05);
            text.setScale(1.05);
        });

        hitArea.on("pointerout", () => {
            button.setScale(1);
            text.setScale(1);
        });

        hitArea.on("pointerdown", () => this.hide());

        this.elements.push(button, text, hitArea);
    }

    hide() {
        this.elements.forEach(el => el.destroy());
        this.elements = [];
    }
}
