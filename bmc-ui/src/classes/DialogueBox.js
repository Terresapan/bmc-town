class DialogueBox {
    constructor(scene, config = {}) {
        this.scene = scene;
        this.awaitingInput = false;
        
        // Set default configuration values
        const {
            x = 512, // Centered horizontally (1024/2)
            y = 600, // Positioned towards bottom
            width = 824,
            height = 200,
            depth = 30
        } = config;
        // Create DOM element
        this.domElement = scene.add.dom(x, y).createFromHTML(`
            <div class="chat-box-container" style="width: ${width}px; height: ${height}px;">
                <textarea class="chat-box-content" readonly></textarea>
            </div>
        `);

        this.domElement.setDepth(depth);
        this.domElement.setScrollFactor(0);
        
        // Store reference to the textarea
        this.textarea = this.domElement.node.querySelector('.chat-box-content');
        this.containerDiv = this.domElement.node.querySelector('.chat-box-container');
        
        // Apply styles to make textarea look like the previous div
        if (this.textarea) {
            this.textarea.style.width = '100%';
            this.textarea.style.height = '100%';
            this.textarea.style.background = 'transparent';
            this.textarea.style.border = 'none';
            this.textarea.style.color = 'inherit'; // Inherit from container
            this.textarea.style.fontFamily = 'inherit'; // Inherit from container
            this.textarea.style.fontSize = 'inherit'; // Inherit from container
            this.textarea.style.lineHeight = 'inherit'; // Inherit from container
            this.textarea.style.resize = 'none';
            this.textarea.style.outline = 'none';
            this.textarea.style.padding = '0'; // Removed extra padding
            this.textarea.style.margin = '0';
            this.textarea.style.boxSizing = 'border-box';

            // Prevent Phaser from capturing keys when focused on textarea
            // This fixes the cursor navigation issues (Arrow keys)
            const stopPropagation = (e) => {
                if (e.key !== 'Escape') {
                    e.stopPropagation();
                }
            };
            
            this.textarea.addEventListener('keydown', stopPropagation);
            this.textarea.addEventListener('keypress', stopPropagation);
            this.textarea.addEventListener('keyup', stopPropagation);
        }
        
        this.hide();
    }
    
    show(message, awaitInput = false) {
        if (this.textarea) {
            this.textarea.value = message;
            
            if (awaitInput) {
                this.textarea.removeAttribute('readonly');
                this.textarea.focus();
                // Ensure text cursor is at the end
                this.textarea.setSelectionRange(message.length, message.length);
            } else {
                this.textarea.setAttribute('readonly', true);
            }
            
            // Auto-scroll to bottom
            this.textarea.scrollTop = this.textarea.scrollHeight;
        }
        
        this.domElement.setVisible(true);
        this.awaitingInput = awaitInput;
    }
    
    getValue() {
        return this.textarea ? this.textarea.value : "";
    }

    clear() {
        if (this.textarea) {
            this.textarea.value = "";
        }
    }
    
    hide() {
        if (this.textarea) {
            this.textarea.blur();
        }
        this.domElement.setVisible(false);
        this.awaitingInput = false;
    }
    
    isVisible() {
        return this.domElement.visible;
    }

    isAwaitingInput() {
        return this.awaitingInput;
    }
}

export default DialogueBox; 