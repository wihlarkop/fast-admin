/**
 * Table Manager - Handles table interactions, sorting, and row selection
 */
class TableManager {
    constructor() {
        this.selectedItems = new Set();
        this.selectAllCheckbox = null;
        this.itemCheckboxes = [];
    }

    init() {
        this.setupTableHoverEffects();
        this.setupCheckboxHandlers();
        this.updateSelectionState();
    }

    /**
     * Add hover effects to table rows
     */
    setupTableHoverEffects() {
        const tableRows = document.querySelectorAll('tbody tr');
        tableRows.forEach(row => {
            row.addEventListener('mouseenter', () => {
                row.classList.add('bg-gray-50');
            });

            row.addEventListener('mouseleave', () => {
                row.classList.remove('bg-gray-50');
            });
        });
    }

    /**
     * Setup checkbox event handlers for bulk selection
     */
    setupCheckboxHandlers() {
        this.selectAllCheckbox = document.querySelector('input[name="select-all"]');
        this.itemCheckboxes = Array.from(document.querySelectorAll('input[name="selected-items"]'));

        // Handle select-all checkbox
        if (this.selectAllCheckbox) {
            this.selectAllCheckbox.addEventListener('change', (event) => {
                this.handleSelectAll(event.target.checked);
            });
        }

        // Handle individual item checkboxes
        this.itemCheckboxes.forEach(checkbox => {
            checkbox.addEventListener('change', (event) => {
                this.handleItemSelection(event.target);
            });
        });
    }

    /**
     * Handle select-all checkbox change
     */
    handleSelectAll(checked) {
        this.itemCheckboxes.forEach(checkbox => {
            checkbox.checked = checked;
            this.updateItemSelection(checkbox);
        });

        this.updateSelectionState();
        this.notifySelectionChange();
    }

    /**
     * Handle individual item selection
     */
    handleItemSelection(checkbox) {
        this.updateItemSelection(checkbox);
        this.updateSelectAllState();
        this.updateSelectionState();
        this.notifySelectionChange();
    }

    /**
     * Update internal selection tracking
     */
    updateItemSelection(checkbox) {
        if (checkbox.checked) {
            this.selectedItems.add(checkbox.value);
        } else {
            this.selectedItems.delete(checkbox.value);
        }
    }

    /**
     * Update select-all checkbox state based on individual selections
     */
    updateSelectAllState() {
        if (!this.selectAllCheckbox) return;

        const checkedCount = this.itemCheckboxes.filter(cb => cb.checked).length;
        const totalCount = this.itemCheckboxes.length;

        if (checkedCount === 0) {
            this.selectAllCheckbox.checked = false;
            this.selectAllCheckbox.indeterminate = false;
        } else if (checkedCount === totalCount) {
            this.selectAllCheckbox.checked = true;
            this.selectAllCheckbox.indeterminate = false;
        } else {
            this.selectAllCheckbox.checked = false;
            this.selectAllCheckbox.indeterminate = true;
        }
    }

    /**
     * Update internal selection state
     */
    updateSelectionState() {
        // Clear and rebuild selected items set
        this.selectedItems.clear();
        this.itemCheckboxes.forEach(checkbox => {
            if (checkbox.checked) {
                this.selectedItems.add(checkbox.value);
            }
        });
    }

    /**
     * Clear all selections
     */
    clearSelection() {
        this.itemCheckboxes.forEach(checkbox => {
            checkbox.checked = false;
        });

        if (this.selectAllCheckbox) {
            this.selectAllCheckbox.checked = false;
            this.selectAllCheckbox.indeterminate = false;
        }

        this.selectedItems.clear();
        this.notifySelectionChange();
    }

    /**
     * Get selected item IDs
     */
    getSelectedItems() {
        return Array.from(this.selectedItems);
    }

    /**
     * Get selected item count
     */
    getSelectedCount() {
        return this.selectedItems.size;
    }

    /**
     * Notify other components about selection changes
     */
    notifySelectionChange() {
        const event = new CustomEvent('table:selectionChanged', {
            detail: {
                selectedItems: this.getSelectedItems(),
                selectedCount: this.getSelectedCount()
            }
        });
        document.dispatchEvent(event);
    }

    /**
     * Check if any items are selected
     */
    hasSelection() {
        return this.selectedItems.size > 0;
    }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TableManager;
}