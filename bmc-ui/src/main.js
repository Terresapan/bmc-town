import { Game } from "./scenes/Game";
import { MainMenu } from "./scenes/MainMenu";
import { Preloader } from "./scenes/Preloader";
import { PauseMenu } from "./scenes/PauseMenu";

console.log("=== MAIN.JS LOADING ===");
console.log("Phaser version:", Phaser.VERSION);

const config = {
  type: Phaser.AUTO,
  width: 1024,
  height: 768,
  parent: "game-container",
  scale: {
    mode: Phaser.Scale.FIT,
    autoCenter: Phaser.Scale.CENTER_BOTH,
  },
  scene: [Preloader, MainMenu, Game, PauseMenu],
  physics: {
    default: "arcade",
    arcade: {
      gravity: { y: 0 },
    },
  },
  dom: {
    createContainer: true,
  },
};

console.log("Creating Phaser game with config:", config);
const game = new Phaser.Game(config);
console.log("Phaser game created:", game);

// Initialize Profile Manager
import profileManager from "./services/ProfileManager";
profileManager.initialize();

export default game;
