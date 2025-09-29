/**
 * QuickExpense Web UI JavaScript
 * Handles file upload, auth status, and results display
 */

class QuickExpenseUI {
    constructor() {
        this.authStatus = null;
        this.isProcessing = false;

        // DOM elements
        this.elements = {
            statusDot: document.getElementById('statusDot'),
            statusText: document.getElementById('statusText'),
            authDetails: document.getElementById('authDetails'),
            connectBtn: document.getElementById('connectBtn'),
            uploadZone: document.getElementById('uploadZone'),
            fileInput: document.getElementById('fileInput'),
            processingState: document.getElementById('processingState'),
            processingMessage: document.getElementById('processingMessage'),
            resultsSection: document.getElementById('resultsSection'),
            errorSection: document.getElementById('errorSection'),
            errorMessage: document.getElementById('errorMessage'),
            receiptInfo: document.getElementById('receiptInfo'),
            businessRules: document.getElementById('businessRules'),
            quickbooksResults: document.getElementById('quickbooksResults'),
            taxSummary: document.getElementById('taxSummary'),
            expenseSummary: document.getElementById('expenseSummary'),
            processAnotherBtn: document.getElementById('processAnotherBtn'),
            tryAgainBtn: document.getElementById('tryAgainBtn')
        };

        this.init();
    }

    init() {
        this.checkAuthStatus();
        this.setupEventListeners();
        this.setupDropZone();
    }

    // ===== AUTH STATUS MANAGEMENT =====

    async checkAuthStatus() {
        try {
            const response = await fetch('/api/web/auth-status');
            const data = await response.json();

            this.authStatus = data;
            this.updateAuthUI(data);
        } catch (error) {
            console.error('Error checking auth status:', error);
            this.updateAuthUI({
                authenticated: false,
                message: 'Unable to check authentication status'
            });
        }
    }

    updateAuthUI(authData) {
        const { statusDot, statusText, authDetails, connectBtn } = this.elements;

        if (authData.authenticated) {
            statusDot.classList.remove('error');
            statusDot.classList.add('connected');
            statusText.textContent = 'Connected to QuickBooks';
            authDetails.textContent = authData.company_name ?
                `Company: ${authData.company_name}` :
                `Company ID: ${authData.company_id || 'Unknown'}`;
            connectBtn.style.display = 'none';
        } else {
            statusDot.classList.remove('connected');
            statusDot.classList.add('error');
            statusText.textContent = 'Not connected to QuickBooks';
            authDetails.textContent = authData.message || 'Authentication required';
            connectBtn.style.display = 'inline-flex';
        }
    }

    async handleConnectClick() {
        try {
            const response = await fetch('/api/web/auth-url');
            const data = await response.json();

            if (data.auth_url) {
                this.openOAuthPopup(data.auth_url);
            } else {
                throw new Error('No authorization URL received');
            }
        } catch (error) {
            console.error('Error getting auth URL:', error);
            this.showError('Failed to initiate QuickBooks connection');
        }
    }

    openOAuthPopup(authUrl) {
        const popup = window.open(
            authUrl,
            'quickbooks_oauth',
            'width=600,height=700,scrollbars=yes,resizable=yes'
        );

        // Listen for messages from popup
        const messageHandler = (event) => {
            if (event.data.type === 'oauth_success') {
                popup.close();
                window.removeEventListener('message', messageHandler);
                this.handleOAuthSuccess();
            } else if (event.data.type === 'oauth_error') {
                popup.close();
                window.removeEventListener('message', messageHandler);
                this.showError('QuickBooks authentication failed');
            }
        };

        window.addEventListener('message', messageHandler);

        // Poll for popup close (fallback)
        const pollTimer = setInterval(() => {
            if (popup.closed) {
                clearInterval(pollTimer);
                window.removeEventListener('message', messageHandler);
                // Check auth status in case popup closed without message
                setTimeout(() => this.checkAuthStatus(), 1000);
            }
        }, 1000);
    }

    handleOAuthSuccess() {
        this.checkAuthStatus();
        this.showSuccessMessage('Successfully connected to QuickBooks!');
    }

    // ===== FILE UPLOAD MANAGEMENT =====

    setupEventListeners() {
        const { connectBtn, uploadZone, fileInput, processAnotherBtn, tryAgainBtn } = this.elements;

        connectBtn.addEventListener('click', () => this.handleConnectClick());
        uploadZone.addEventListener('click', () => this.handleUploadClick());
        fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        processAnotherBtn.addEventListener('click', () => this.resetToUpload());
        tryAgainBtn.addEventListener('click', () => this.resetToUpload());
    }

    setupDropZone() {
        const { uploadZone } = this.elements;

        // Prevent default drag behaviors
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            uploadZone.addEventListener(eventName, this.preventDefaults, false);
            document.body.addEventListener(eventName, this.preventDefaults, false);
        });

        // Highlight drop zone when item is dragged over it
        ['dragenter', 'dragover'].forEach(eventName => {
            uploadZone.addEventListener(eventName, () => this.highlight(), false);
        });

        ['dragleave', 'drop'].forEach(eventName => {
            uploadZone.addEventListener(eventName, () => this.unhighlight(), false);
        });

        // Handle dropped files
        uploadZone.addEventListener('drop', (e) => this.handleDrop(e), false);
    }

    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }

    highlight() {
        this.elements.uploadZone.classList.add('drag-over');
    }

    unhighlight() {
        this.elements.uploadZone.classList.remove('drag-over');
    }

    handleUploadClick() {
        if (!this.isProcessing) {
            this.elements.fileInput.click();
        }
    }

    handleDrop(e) {
        const dt = e.dataTransfer;
        const files = dt.files;

        if (files.length > 0) {
            this.processFile(files[0]);
        }
    }

    handleFileSelect(e) {
        const files = e.target.files;
        if (files.length > 0) {
            this.processFile(files[0]);
        }
    }

    // ===== FILE VALIDATION =====

    validateFile(file) {
        // Check if file exists
        if (!file) {
            throw new Error('No file selected. Please choose a receipt file to upload.');
        }

        // Check file name
        if (!file.name || file.name.trim() === '') {
            throw new Error('Invalid file. Please select a valid receipt file.');
        }

        const supportedTypes = [
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif',
            'image/bmp', 'image/webp', 'application/pdf'
        ];

        const supportedExtensions = [
            '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.pdf', '.heic', '.heif'
        ];

        const maxSize = 10 * 1024 * 1024; // 10MB
        const minSize = 1024; // 1KB minimum

        // Check file size
        if (file.size === 0) {
            throw new Error('File appears to be empty. Please select a valid receipt file.');
        }

        if (file.size < minSize) {
            throw new Error('File too small. Please select a valid receipt image or PDF.');
        }

        if (file.size > maxSize) {
            const maxSizeMB = Math.round(maxSize / (1024 * 1024));
            const fileSizeMB = Math.round(file.size / (1024 * 1024) * 10) / 10;
            throw new Error(`File too large (${fileSizeMB}MB). Maximum size is ${maxSizeMB}MB.`);
        }

        // Check file type and extension
        const fileName = file.name.toLowerCase();
        const hasValidExtension = supportedExtensions.some(ext => fileName.endsWith(ext));
        const hasValidType = supportedTypes.includes(file.type) || fileName.endsWith('.heic') || fileName.endsWith('.heif');

        if (!hasValidExtension && !hasValidType) {
            throw new Error(`Unsupported file format "${file.name.split('.').pop()?.toUpperCase() || 'unknown'}". Please use JPEG, PNG, PDF, or HEIC files.`);
        }

        // Additional validation for suspicious files
        const suspiciousExtensions = ['.exe', '.bat', '.cmd', '.com', '.scr', '.pif', '.jar'];
        const isSuspicious = suspiciousExtensions.some(ext => fileName.endsWith(ext));

        if (isSuspicious) {
            throw new Error('Invalid file type. Please upload only receipt images or PDFs.');
        }

        return true;
    }

    // ===== FILE PROCESSING =====

    async processFile(file) {
        if (this.isProcessing) return;

        try {
            // Check authentication first
            if (!this.authStatus?.authenticated) {
                this.showError('Please connect to QuickBooks before uploading receipts. Click the "Connect to QuickBooks" button above.');
                return;
            }

            // Validate file
            this.validateFile(file);

            // Start processing
            this.isProcessing = true;
            this.showProcessing(`Extracting data from ${file.name}...`);

            // Prepare form data
            const formData = new FormData();
            formData.append('file', file);
            formData.append('category', '');
            formData.append('additional_context', '');

            // Update processing message
            setTimeout(() => {
                if (this.isProcessing) {
                    this.elements.processingMessage.textContent = 'Analyzing receipt with AI...';
                }
            }, 2000);

            setTimeout(() => {
                if (this.isProcessing) {
                    this.elements.processingMessage.textContent = 'Applying business rules...';
                }
            }, 4000);

            setTimeout(() => {
                if (this.isProcessing) {
                    this.elements.processingMessage.textContent = 'Creating expense in QuickBooks...';
                }
            }, 6000);

            // Upload and process with timeout
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 60000); // 60 second timeout

            let response;
            try {
                response = await fetch('/api/web/upload-receipt', {
                    method: 'POST',
                    body: formData,
                    signal: controller.signal
                });
                clearTimeout(timeoutId);
            } catch (fetchError) {
                clearTimeout(timeoutId);

                if (fetchError.name === 'AbortError') {
                    throw new Error('Upload timed out. Please try again with a smaller file or check your internet connection.');
                }

                if (!navigator.onLine) {
                    throw new Error('No internet connection. Please check your network and try again.');
                }

                throw new Error('Network error. Please check your connection and try again.');
            }

            // Handle response
            if (!response.ok) {
                let errorMessage = `Server error (${response.status})`;

                try {
                    const errorData = await response.json();
                    errorMessage = errorData.detail || errorData.message || errorMessage;

                    // Handle specific error types
                    if (response.status === 401 || response.status === 403) {
                        errorMessage = 'Authentication expired. Please reconnect to QuickBooks.';
                        // Refresh auth status
                        this.checkAuthStatus();
                    } else if (response.status === 413) {
                        errorMessage = 'File too large for server. Please use a smaller file.';
                    } else if (response.status === 422) {
                        errorMessage = 'Invalid file format or corrupted file. Please try a different file.';
                    } else if (response.status === 500) {
                        errorMessage = 'Server error while processing. Please try again in a moment.';
                    }

                } catch (parseError) {
                    console.warn('Could not parse error response:', parseError);
                }

                throw new Error(errorMessage);
            }

            const result = await response.json();

            // Validate response structure
            if (!result || typeof result !== 'object') {
                throw new Error('Invalid response from server. Please try again.');
            }

            if (result.status !== 'success') {
                throw new Error(result.message || 'Processing failed. Please try again.');
            }

            this.showResults(result);

        } catch (error) {
            console.error('Error processing file:', error);

            // Provide user-friendly error messages
            let userMessage = error.message;

            // Handle common error patterns
            if (userMessage.toLowerCase().includes('token') || userMessage.toLowerCase().includes('auth')) {
                userMessage = 'Authentication issue. Please reconnect to QuickBooks and try again.';
                this.checkAuthStatus(); // Refresh auth status
            } else if (userMessage.toLowerCase().includes('network') || userMessage.toLowerCase().includes('fetch')) {
                userMessage = 'Network error. Please check your internet connection and try again.';
            } else if (userMessage.toLowerCase().includes('timeout')) {
                userMessage = 'Upload timed out. Please try again with a smaller file.';
            } else if (userMessage.toLowerCase().includes('gemini') || userMessage.toLowerCase().includes('ai')) {
                userMessage = 'AI processing error. Please try again or use a clearer receipt image.';
            } else if (userMessage.toLowerCase().includes('quickbooks')) {
                userMessage = 'QuickBooks integration error. Please verify your connection and try again.';
            }

            this.showError(userMessage || 'An unexpected error occurred while processing your receipt.');
        } finally {
            this.isProcessing = false;
        }
    }

    // ===== UI STATE MANAGEMENT =====

    showProcessing(message) {
        const { uploadZone, processingState, processingMessage, resultsSection, errorSection } = this.elements;

        uploadZone.style.display = 'none';
        processingState.style.display = 'block';
        resultsSection.style.display = 'none';
        errorSection.style.display = 'none';

        processingMessage.textContent = message;
    }

    showResults(data) {
        const { uploadZone, processingState, resultsSection, errorSection } = this.elements;

        uploadZone.style.display = 'none';
        processingState.style.display = 'none';
        resultsSection.style.display = 'block';
        errorSection.style.display = 'none';

        this.populateResults(data);
    }

    showError(message) {
        const { uploadZone, processingState, resultsSection, errorSection, errorMessage } = this.elements;

        uploadZone.style.display = 'block';
        processingState.style.display = 'none';
        resultsSection.style.display = 'none';
        errorSection.style.display = 'block';

        errorMessage.textContent = message;
    }

    resetToUpload() {
        const { uploadZone, processingState, resultsSection, errorSection, fileInput } = this.elements;

        uploadZone.style.display = 'flex';
        processingState.style.display = 'none';
        resultsSection.style.display = 'none';
        errorSection.style.display = 'none';

        // Reset file input
        fileInput.value = '';
        this.isProcessing = false;
    }

    showSuccessMessage(message) {
        // Create temporary success notification
        const notification = document.createElement('div');
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: var(--status-success);
            color: white;
            padding: 1rem 1.5rem;
            border-radius: var(--radius-md);
            z-index: 1000;
            animation: slideIn 0.3s ease;
        `;
        notification.textContent = message;

        document.body.appendChild(notification);

        setTimeout(() => {
            notification.remove();
        }, 3000);
    }

    // ===== RESULTS DISPLAY =====

    populateResults(data) {
        this.populateReceiptInfo(data.receipt_info);
        this.populateBusinessRules(data.business_rules);
        this.populateTaxSummary(data.tax_deductibility);
        this.populateExpenseSummary(data.enhanced_expense);
        this.populateQuickBooksResults(data.quickbooks);
    }

    populateReceiptInfo(receiptInfo) {
        const container = this.elements.receiptInfo;
        container.innerHTML = '';

        // Match CLI format exactly
        const items = [
            { label: 'File:', value: receiptInfo.filename || 'Unknown' },
            { label: 'Vendor:', value: receiptInfo.vendor_name || 'Unknown' },
            { label: 'Date:', value: receiptInfo.date ? new Date(receiptInfo.date).toLocaleDateString('en-CA') : 'Unknown' },
            { label: 'Total Amount:', value: `$${receiptInfo.total_amount?.toFixed(2) || '0.00'}` },
            { label: 'Tax:', value: `$${receiptInfo.tax_amount?.toFixed(2) || '0.00'}` },
            { label: 'Currency:', value: receiptInfo.currency || 'CAD' }
        ];

        items.forEach(item => {
            const element = this.createInfoItem(item.label, item.value);
            container.appendChild(element);
        });
    }

    populateBusinessRules(businessRules) {
        const container = this.elements.businessRules;
        container.innerHTML = '';

        if (businessRules.applied_rules && businessRules.applied_rules.length > 0) {
            businessRules.applied_rules.forEach((rule, index) => {
                // Create a rule block matching CLI format
                const ruleBlock = document.createElement('div');
                ruleBlock.className = 'rule-block';

                // Rule title (match CLI: "📄 Restaurant meal consolidation")
                const title = document.createElement('div');
                title.className = 'rule-title';
                title.textContent = `📄 ${rule.description}`;
                ruleBlock.appendChild(title);

                // Rule details (match CLI format exactly)
                const details = [
                    `Rule Applied: ${rule.rule_applied}`,
                    `Category: ${rule.category}`,
                    `QuickBooks Account: ${rule.qb_account}`,
                    `Tax Deductible: ${rule.deductible_percentage}%`,
                    `Tax Treatment: ${rule.tax_treatment || 'standard'}`,
                    `Confidence: ${((rule.confidence || 0) * 100).toFixed(0)}%`
                ];

                details.forEach(detail => {
                    const detailDiv = document.createElement('div');
                    detailDiv.className = 'rule-details';
                    detailDiv.textContent = detail;
                    ruleBlock.appendChild(detailDiv);
                });

                // Success indicator (match CLI: "✅ Matched Rule")
                const indicator = document.createElement('div');
                indicator.className = 'rule-indicator';
                indicator.textContent = '✅ Matched Rule';
                ruleBlock.appendChild(indicator);

                container.appendChild(ruleBlock);
            });
        } else {
            const element = this.createInfoItem('Rules Applied', 'None');
            container.appendChild(element);
        }
    }

    populateTaxSummary(taxData) {
        const container = this.elements.taxSummary;
        container.innerHTML = '';

        if (taxData) {
            const items = [
                { label: 'Total Amount:', value: `$${taxData.total_amount}` },
                { label: 'Deductible Amount:', value: `$${taxData.deductible_amount} (${taxData.deductibility_rate}%)` }
            ];

            items.forEach(item => {
                const element = this.createInfoItem(item.label, item.value);
                container.appendChild(element);
            });
        }
    }

    populateExpenseSummary(expenseData) {
        const container = this.elements.expenseSummary;
        container.innerHTML = '';

        if (expenseData) {
            const items = [
                { label: 'Vendor:', value: expenseData.vendor_name || 'Unknown' },
                { label: 'Items:', value: `${expenseData.items_count}, Categories: ${expenseData.categories_count}` },
                { label: 'Business Rules Applied:', value: expenseData.rules_applied || '0' },
                { label: 'Payment:', value: expenseData.payment || 'cash' }
            ];

            items.forEach(item => {
                const element = this.createInfoItem(item.label, item.value);
                container.appendChild(element);
            });
        }
    }

    populateQuickBooksResults(qbResults) {
        const container = this.elements.quickbooksResults;
        container.innerHTML = '';

        // Match CLI format exactly
        if (qbResults && qbResults.expense_ids && qbResults.expense_ids.length > 0) {
            const successMsg = document.createElement('div');
            successMsg.className = 'qb-success';
            successMsg.textContent = `Successfully created expense in QuickBooks (ID: ${qbResults.expense_ids.join(', ')})`;
            container.appendChild(successMsg);
        } else {
            container.textContent = 'No expenses created';
        }
    }

    createInfoItem(label, value) {
        const item = document.createElement('div');
        item.className = 'info-item';

        const labelSpan = document.createElement('span');
        labelSpan.className = 'info-label';
        labelSpan.textContent = label;

        const valueSpan = document.createElement('span');
        valueSpan.className = 'info-value';
        valueSpan.textContent = value;

        item.appendChild(labelSpan);
        item.appendChild(valueSpan);

        return item;
    }

    formatCurrency(amount) {
        if (amount === null || amount === undefined) return '$0.00';
        return new Intl.NumberFormat('en-CA', {
            style: 'currency',
            currency: 'CAD'
        }).format(amount);
    }
}

// Initialize the application when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new QuickExpenseUI();
});

// Add CSS for notifications
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
`;
document.head.appendChild(style);
