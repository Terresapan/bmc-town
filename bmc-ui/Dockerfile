#
# --- THIS IS YOUR DEVELOPMENT DOCKERFILE ---
#

FROM node:18

# Set the working directory
WORKDIR /app

# Copy package files and install dependencies
# We copy this first to cache the 'npm install' layer
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy project files
COPY . .

# Expose the port your dev server uses (8080 matches your compose file)
EXPOSE 8080

# --- UPDATED COMMAND ---
# We call webpack-dev-server directly from node_modules
# - We add "--host 0.0.0.0" to make it accessible from your Mac.
# - We remove the "--open" flag, which would crash the container.
CMD ["./node_modules/.bin/webpack-dev-server", "--config", "webpack/config.js", "--host", "0.0.0.0"]