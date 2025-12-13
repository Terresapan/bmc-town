export class Dropdown {
    constructor(scene, x, y, width, height, items, onSelect) {
        this.scene = scene;
        this.x = x;
        this.y = y;
        this.width = width;
        this.height = height;
        this.items = items;
        this.onSelect = onSelect;
        this.isOpen = false;
        this.selectedIndex = 0;
        this.elements = [];
        
        // Scrolling properties
        this.maxItems = 4;
        this.scrollIndex = 0;
        
        this.create();
    }

    create() {
        // Create dropdown background
        const dropdownBg = this.scene.add.graphics();
        dropdownBg.fillStyle(0xffffff, 1);
        dropdownBg.fillRoundedRect(
            this.x - this.width / 2,
            this.y - this.height / 2,
            this.width,
            this.height,
            8
        );
        dropdownBg.lineStyle(2, 0x000000, 1);
        dropdownBg.strokeRoundedRect(
            this.x - this.width / 2,
            this.y - this.height / 2,
            this.width,
            this.height,
            8
        );

        // Create dropdown text
        const initialText = this.items.length > 0 ? this.items[0] : "Loading...";
        this.text = this.scene.add.text(
            this.x - this.width / 2 + 15,
            this.y,
            initialText,
            {
                fontSize: "16px",
                fontFamily: "Arial",
                color: "#000000",
            }
        ).setOrigin(0, 0.5);

        // Create dropdown arrow
        const arrowSize = 8;
        const arrow = this.scene.add.graphics();
        arrow.fillStyle(0x000000, 1);
        arrow.fillTriangle(
            this.x + this.width / 2 - 25,
            this.y - arrowSize / 2,
            this.x + this.width / 2 - 25 + arrowSize,
            this.y - arrowSize / 2,
            this.x + this.width / 2 - 25 + arrowSize / 2,
            this.y + arrowSize / 2
        );

        // Make dropdown clickable
        const hitArea = this.scene.add.rectangle(
            this.x,
            this.y,
            this.width,
            this.height,
            0x000000,
            0
        ).setInteractive();

        hitArea.on("pointerdown", () => this.toggle());
        
        // Mouse wheel support
        this.scene.input.on('wheel', (pointer, gameObjects, deltaX, deltaY, deltaZ) => {
            if (this.isOpen) {
                if (deltaY > 0) {
                    // Scroll down
                    if (this.scrollIndex + this.maxItems < this.items.length) {
                        this.scrollIndex++;
                        this.refreshList();
                    }
                } else if (deltaY < 0) {
                    // Scroll up
                    if (this.scrollIndex > 0) {
                        this.scrollIndex--;
                        this.refreshList();
                    }
                }
            }
        });

        this.mainElements = [dropdownBg, this.text, arrow, hitArea];
    }

    toggle() {
        if (this.isOpen) {
            this.close();
        } else {
            this.open();
        }
    }

    open() {
        this.isOpen = true;
        const itemHeight = 35;
        
        // Determine how many items to show
        const visibleCount = Math.min(this.items.length, this.maxItems);
        const dropdownHeight = visibleCount * itemHeight;
        
        // Calculate the slice of items to show
        const visibleItems = this.items.slice(this.scrollIndex, this.scrollIndex + visibleCount);

        // Create list background
        const listBg = this.scene.add.graphics();
        listBg.fillStyle(0xffffff, 1);
        listBg.fillRoundedRect(
            this.x - this.width / 2,
            this.y + this.height / 2,
            this.width,
            dropdownHeight,
            8
        );
        listBg.lineStyle(2, 0x000000, 1);
        listBg.strokeRoundedRect(
            this.x - this.width / 2,
            this.y + this.height / 2,
            this.width,
            dropdownHeight,
            8
        );
        this.elements.push(listBg);

        // Create items
        visibleItems.forEach((item, i) => {
            const realIndex = this.scrollIndex + i;
            const itemY = this.y + this.height / 2 + i * itemHeight + itemHeight / 2;

            // Item background
            const itemBg = this.scene.add.graphics();
            this.drawItemBg(itemBg, realIndex === this.selectedIndex, itemY, itemHeight);
            
            // Item text
            const itemText = this.scene.add.text(
                this.x - this.width / 2 + 15,
                itemY,
                item,
                {
                    fontSize: "16px",
                    fontFamily: "Arial",
                    color: "#000000",
                }
            ).setOrigin(0, 0.5);

            // Click area
            const itemArea = this.scene.add.rectangle(
                this.x,
                itemY,
                this.width,
                itemHeight,
                0x000000,
                0
            ).setInteractive();

            itemArea.on("pointerdown", () => {
                this.select(realIndex);
            });

            itemArea.on("pointerover", () => {
                this.drawItemBg(itemBg, true, itemY, itemHeight, true);
            });

            itemArea.on("pointerout", () => {
                this.drawItemBg(itemBg, realIndex === this.selectedIndex, itemY, itemHeight);
            });

            this.elements.push(itemBg, itemText, itemArea);
        });

        // Add Scroll Arrows if needed
        if (this.items.length > this.maxItems) {
            this.createScrollControls(dropdownHeight);
        }
    }

    createScrollControls(dropdownHeight) {
        const arrowX = this.x + this.width / 2 - 20;
        const topY = this.y + this.height / 2 + 15;
        const bottomY = this.y + this.height / 2 + dropdownHeight - 15;

        // Up Arrow
        if (this.scrollIndex > 0) {
            const upArrow = this.scene.add.text(arrowX, topY, "▲", { fontSize: "16px", color: "#000000" }).setOrigin(0.5).setInteractive();
            upArrow.on('pointerdown', () => {
                this.scrollIndex--;
                this.refreshList();
            });
            this.elements.push(upArrow);
        }

        // Down Arrow
        if (this.scrollIndex + this.maxItems < this.items.length) {
            const downArrow = this.scene.add.text(arrowX, bottomY, "▼", { fontSize: "16px", color: "#000000" }).setOrigin(0.5).setInteractive();
            downArrow.on('pointerdown', () => {
                this.scrollIndex++;
                this.refreshList();
            });
            this.elements.push(downArrow);
        }
    }

    refreshList() {
        // Clear current list elements but keep main elements
        this.elements.forEach(el => el.destroy());
        this.elements = [];
        this.open();
    }

    drawItemBg(graphics, isSelected, y, height, isHover = false) {
        graphics.clear();
        if (isHover) {
            graphics.fillStyle(0xfbcfe8, 1); // Light pink (pink-200)
        } else if (isSelected) {
            graphics.fillStyle(0xe6f3ff, 1);
        } else {
            graphics.fillStyle(0xffffff, 1);
        }
        graphics.fillRect(
            this.x - this.width / 2 + 2,
            y - height / 2 + 2,
            this.width - 4,
            height - 2
        );
    }

    close() {
        this.isOpen = false;
        this.elements.forEach(el => el.destroy());
        this.elements = [];
    }

    select(index) {
        this.selectedIndex = index;
        this.text.setText(this.items[index]);
        this.close();
        if (this.onSelect) {
            this.onSelect(index, this.items[index]);
        }
    }

    updateItems(items) {
        this.items = items;
        this.scrollIndex = 0; // Reset scroll on update
        if (this.items.length > 0) {
            if (this.selectedIndex >= this.items.length) {
                this.selectedIndex = 0;
            }
            this.text.setText(this.items[this.selectedIndex]);
        } else {
            this.text.setText("No items found");
        }
    }

    destroy() {
        this.close();
        this.mainElements.forEach(el => el.destroy());
    }
}
