/**
 * Bulk Actions Manager - Handles bulk operations on selected table items
 */
class BulkActions {
    constructor() {
        this.bulkActionsContainer = null;
        this.selectedCountElement = null;
        this.isVisible = false;
    }

    init() {
        this.setupBulkActionsContainer();
        this.setupEventListeners();
        this.updateVisibility(0);
    }

    /**
     * Setup bulk actions container and elements
     */
    setupBulkActionsContainer() {
        this.bulkActionsContainer = document.querySelector('.bulk-actions');
        this.selectedCountElement = document.querySelector('.selected-count');

        if (!this.bulkActionsContainer) {
            console.warn('Bulk actions container not found');
            return;
        }

        // Setup clear selection button
        const clearButton = this.bulkActionsContainer.querySelector('[onclick="clearSelection()"]');
        if (clearButton) {
            clearButton.removeAttribute('onclick');
            clearButton.addEventListener('click', () => this.clearSelection());
        }
    }

    /**
     * Setup event listeners
     */
    setupEventListeners() {
        // Listen for table selection changes
        document.addEventListener('table:selectionChanged', (event) => {
            this.handleSelectionChange(event.detail);
        });

        // Setup bulk delete confirmation
        this.setupBulkDeleteHandler();
    }

    /**
     * Handle selection changes from table manager
     */
    handleSelectionChange(selectionData) {
        const { selectedCount } = selectionData;
        this.updateVisibility(selectedCount);
        this.updateSelectedCount(selectedCount);
    }

    /**
     * Update bulk actions visibility based on selection count
     */
    updateVisibility(selectedCount) {
        if (!this.bulkActionsContainer) return;

        const shouldShow = selectedCount > 0;
        
        if (shouldShow !== this.isVisible) {
            this.isVisible = shouldShow;
            this.bulkActionsContainer.style.display = shouldShow ? 'block' : 'none';
            
            // Add animation class for smooth transitions
            if (shouldShow) {
                this.bulkActionsContainer.classList.add('fade-in');
            } else {
                this.bulkActionsContainer.classList.remove('fade-in');
            }
        }
    }

    /**
     * Update selected count display
     */
    updateSelectedCount(count) {
        if (this.selectedCountElement) {
            this.selectedCountElement.textContent = count;
        }
    }

    /**
     * Setup bulk delete handler with enhanced confirmation
     */
    setupBulkDeleteHandler() {
        const deleteButton = document.querySelector('[hx-post*="/bulk-delete/"]');
        if (!deleteButton) return;

        // Override HTMX confirm with custom handler
        deleteButton.addEventListener('htmx:confirm', (event) => {
            event.preventDefault();
            this.confirmBulkDelete().then(confirmed => {
                if (confirmed) {
                    event.detail.issueRequest();
                }
            });
        });
    }

    /**
     * Enhanced bulk delete confirmation
     */
    async confirmBulkDelete() {
        const selectedCount = document.querySelectorAll('input[name="selected-items"]:checked').length;
        
        const message = selectedCount === 1 
            ? 'Are you sure you want to delete this item?'
            : `Are you sure you want to delete these ${selectedCount} items?`;

        // Use custom modal if available, fallback to confirm
        if (typeof this.showCustomConfirm === 'function') {
            return await this.showCustomConfirm(message, 'Delete Items', 'destructive');
        }
        
        return confirm(message);
    }

    /**
     * Clear all selections
     */
    clearSelection() {
        // Dispatch event to table manager
        const event = new CustomEvent('bulkActions:clearSelection');
        document.dispatchEvent(event);
        
        // Also trigger table manager directly if available
        if (window.fastAdmin?.tableManager) {
            window.fastAdmin.tableManager.clearSelection();
        }
    }

    /**
     * Execute bulk action with loading state
     */
    async executeBulkAction(actionType, selectedItems) {
        if (selectedItems.length === 0) {
            this.showNotification('No items selected', 'warning');
            return;
        }

        // Show loading state
        this.setLoadingState(true);

        try {
            // The actual request will be handled by HTMX
            // This is just for UI feedback
            this.showNotification(`Processing ${selectedItems.length} items...`, 'info');
        } catch (error) {
            console.error('Bulk action failed:', error);
            this.showNotification('Action failed. Please try again.', 'error');
        } finally {
            this.setLoadingState(false);
        }
    }

    /**
     * Set loading state for bulk actions
     */
    setLoadingState(loading) {
        if (!this.bulkActionsContainer) return;

        const buttons = this.bulkActionsContainer.querySelectorAll('button');
        buttons.forEach(button => {
            if (loading) {
                button.disabled = true;
                button.classList.add('opacity-50', 'cursor-not-allowed');
            } else {
                button.disabled = false;
                button.classList.remove('opacity-50', 'cursor-not-allowed');
            }
        });
    }

    /**
     * Show notification to user
     */
    showNotification(message, type = 'info') {
        // Create a simple notification
        const notification = document.createElement('div');
        notification.className = `alert alert-${type} fixed top-4 right-4 z-50 max-w-md`;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 1000;
            min-width: 300px;
        `;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        // Auto-remove after 3 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 3000);
    }

    /**
     * Get currently selected items count
     */
    getSelectedCount() {
        return document.querySelectorAll('input[name="selected-items"]:checked').length;
    }

    /**
     * Check if bulk actions are currently visible
     */
    isVisible() {
        return this.isVisible;
    }
}

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = BulkActions;
}