# Business Model Canvas Town 📖

![Business Model Canvas Agents Town](public/assets/game_screenshot.png)

Business Model Canvas Town is an interactive visual interface that gamifies the process of building a business model. 

# Overview

This web-based game features a charming pixel-art town where you can explore and engage with "Business Experts"—specialized AI agents representing the nine building blocks of the Business Model Canvas (e.g., Customer Segments, Value Propositions).

The UI is built with Phaser 3, a powerful HTML5 game framework, and connects to a backend API that powers the Business Experts' conversational abilities using LangGraph and Google Gemini.

# Getting Started

## Requirements

[Node.js](https://nodejs.org) is required to install dependencies and run scripts via `npm`. If you don't want to install Node.js, you can use the provided Docker container.

## Available Commands

| Command               | Description                                                                                              |
| --------------------- | -------------------------------------------------------------------------------------------------------- |
| `npm install`         | Install project dependencies                                                                             |
| `npm run dev`         | Launch a development web server                                                                          |
| `npm run build`       | Create a production build in the `dist` folder                                                           |

## Setting up the UI

After cloning the repo, run npm install from your project directory. Then, you can start the local development server by running npm run dev.

```bash
cd bmc-ui
npm install
npm run dev
```

The local development server runs on http://localhost:8080 by default.

# Features

## Interactive Town Environment

Explore a charming pixel-art town with various buildings and natural elements.

![Business Model Canvas Agents Town](public/assets/philoagents_town.png)

To build the town, we have used the following assets:

- [Tuxemon](https://github.com/Tuxemon/Tuxemon)
- [LPC Plant Repack](https://opengameart.org/content/lpc-plant-repack)
- [LPC Compatible Ancient Greek Architecture](https://opengameart.org/content/lpc-compatible-ancient-greek-architecture)

## Business Experts

Interact with specialized agents like "Steven Segments" (Customer Segments), "Victor Value" (Value Propositions), and "Chloe Channels" (Channels). These experts guide you through completing each section of your business model.

The character sprites are based on philosopher archetypes but have been repurposed to represent these modern business roles.

![Business Model Canvas Agents Sprite](public/assets/sprite_image.png)

## Dialogue System

Engage in multimodal conversations (text + images/PDFs) with the experts. The dialogue system is controlled by the [DialogueBox](src/classes/DialogueBox.js) and [DialogueManager](src/classes/DialogueManager.js) classes.

## Dynamic Movement

Characters roam around the town with realistic movement patterns and collision detection. This is implemented in the [Character](src/classes/Character.js) class.

# Project Structure

- `index.html` - A basic HTML page to contain the game.
- `src` - Contains the game source code.
- `src/main.js` - The main entry point. This contains the game configuration and starts the game.
- `src/scenes/` - The Phaser Scenes are in this folder.
- `public/style.css` - Some simple CSS rules to help with page layout.
- `public/assets` - Contains the static assets used by the game.

# Docker

The project includes Docker support for easy deployment. You can use the following commands to run the UI with Docker:

```bash
# Build the Docker image
docker build -t bmc-ui .

# Run the container
docker run -p 8080:8080 bmc-ui
```

**Note:** This is just the UI. For a complete experience, ensure the backend API is running. Use the root-level `docker-compose.yml` to start both services together.

# Controls

- **Arrow keys:** Move your character around the town
- **Space:** Interact with Business Experts when you're close to them
- **ESC:** Close dialogue windows or open the pause menu

# Contributing

Contributions are welcome! Please feel free to submit a Pull Request.