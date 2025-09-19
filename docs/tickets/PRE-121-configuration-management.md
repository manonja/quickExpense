# PRE-121: Configuration Management for Business Context

**Type:** Enhancement
**Priority:** Low (Convenience)
**Effort:** 1 Story Point
**Sprint:** Phase 1 - Enhanced User Experience

## User Story
**As a** sole proprietor using the system regularly
**I want** to set my business details once (BC location, business type, default payment method)
**So that** the system automatically applies the right context to all receipts without repetitive data entry

## Business Value
- **Problem:** Users must manually specify business context for each receipt processing
- **Impact:** Repetitive data entry, potential inconsistency, poor user experience
- **Solution:** Configurable business context with automatic application and override capability

## Description
Implement a configuration management system that allows users to set default business context, processing preferences, and system settings. The system should automatically apply these defaults while allowing per-receipt overrides when needed.

## Configuration Requirements
**Business Context Settings:**
- Business entity type (sole_proprietorship, corporation, partnership)
- Default province/territory (BC, ON, etc.)
- Business type (consulting, retail, professional services)
- Default payment methods (corporate credit card, business account)
- Default currency (CAD, USD)
- Business industry for specialized rules
- Tax form mapping (T2125 for sole proprietors)

**Processing Preferences:**
- Default output format (human-readable, JSON)
- Dry-run preferences for new users
- Audit log retention settings
- Batch processing defaults

## Acceptance Criteria

### AC1: Configuration Storage and Management
- [ ] Store configuration in user-specific config file
- [ ] Support both global and user-level configurations
- [ ] Validate configuration values against known options
- [ ] Provide default fallbacks for missing configuration
- [ ] Support configuration file versioning and migration

### AC2: Business Context Configuration
- [ ] Set default province for provincial tax calculations
- [ ] Configure business type for specialized business rules
- [ ] Set default payment methods for expense categorization
- [ ] Configure industry-specific settings
- [ ] Support multiple business profiles (if user has multiple businesses)

### AC3: CLI Configuration Commands
- [ ] Implement `quickexpense config` command set
- [ ] Support setting individual configuration values
- [ ] Provide configuration validation and help
- [ ] Show current configuration status
- [ ] Allow configuration reset to defaults

### AC4: Automatic Application
- [ ] Apply default business context to all processing
- [ ] Allow per-receipt override of defaults
- [ ] Show applied configuration in processing output
- [ ] Log configuration usage for audit trail
- [ ] Handle missing or invalid configuration gracefully

### AC5: Configuration Migration and Validation
- [ ] Validate configuration on startup
- [ ] Migrate configuration between system versions
- [ ] Provide helpful error messages for invalid config
- [ ] Support configuration export/import for backup
- [ ] Warn about deprecated configuration options

## Technical Implementation

### Files to Create/Modify
- `src/quickexpense/core/config_manager.py` - New configuration management
- `src/quickexpense/models/config.py` - Configuration models
- `src/quickexpense/cli.py` - Configuration commands
- `src/quickexpense/core/config.py` - Enhanced settings integration
- `tests/core/test_config_manager.py` - Comprehensive tests

### ConfigurationManager
```python
class ConfigurationManager:
    """Manage user configuration and business context."""

    def __init__(self, config_path: Path | None = None):
        self.config_path = config_path or self._get_default_config_path()
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config: UserConfiguration | None = None

    def load_configuration(self) -> UserConfiguration:
        """Load user configuration from file."""

        if self._config:
            return self._config

        if not self.config_path.exists():
            # Create default configuration
            self._config = UserConfiguration()
            self.save_configuration(self._config)
            return self._config

        try:
            with open(self.config_path) as f:
                config_data = json.load(f)

            # Validate and migrate if needed
            config_data = self._migrate_configuration(config_data)
            self._config = UserConfiguration.model_validate(config_data)

            return self._config

        except Exception as e:
            logger.warning(f"Failed to load configuration: {e}")
            # Fall back to defaults
            self._config = UserConfiguration()
            return self._config

    def save_configuration(self, config: UserConfiguration) -> None:
        """Save configuration to file."""

        try:
            # Atomic write
            temp_path = self.config_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                json.dump(
                    config.model_dump(exclude_none=True),
                    f,
                    indent=2,
                    default=str
                )

            temp_path.rename(self.config_path)
            self._config = config

            logger.info(f"Configuration saved to {self.config_path}")

        except Exception as e:
            logger.error(f"Failed to save configuration: {e}")
            raise ConfigurationError(f"Could not save configuration: {e}") from e

    def get_business_context(self) -> BusinessContext:
        """Get current business context for processing."""

        config = self.load_configuration()

        return BusinessContext(
            province=config.business.default_province,
            business_type=config.business.business_type,
            industry=config.business.industry,
            default_payment_method=config.business.default_payment_method,
            default_currency=config.business.default_currency
        )

    def update_setting(self, key: str, value: Any) -> None:  # noqa: ANN401
        """Update specific configuration setting."""

        config = self.load_configuration()

        # Parse nested keys (e.g., "business.default_province")
        keys = key.split('.')
        target = config

        for k in keys[:-1]:
            target = getattr(target, k)

        # Validate value before setting
        final_key = keys[-1]
        self._validate_setting_value(final_key, value, target)

        setattr(target, final_key, value)
        self.save_configuration(config)

class UserConfiguration(BaseModel):
    """Complete user configuration."""

    version: str = "1.0"
    business: BusinessConfiguration = Field(default_factory=BusinessConfiguration)
    processing: ProcessingConfiguration = Field(default_factory=ProcessingConfiguration)
    system: SystemConfiguration = Field(default_factory=SystemConfiguration)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

class BusinessConfiguration(BaseModel):
    """Business context configuration."""

    entity_type: str = "sole_proprietorship"  # sole_proprietorship, corporation, partnership
    default_province: str = "BC"  # Default to BC as specified
    business_type: str = "consulting"  # consulting, retail, professional_services
    industry: str | None = None  # technology, healthcare, etc.
    default_payment_method: str = "credit_card"  # credit_card, bank_transfer, cash
    default_currency: str = "CAD"
    business_name: str | None = None
    business_number: str | None = None  # CRA business number
    gst_number: str | None = None  # GST/HST registration number

    @property
    def tax_form(self) -> str:
        """Get tax form based on entity type."""
        return {
            "sole_proprietorship": "T2125",
            "corporation": "T2",
            "partnership": "T5013"
        }.get(self.entity_type, "T2125")

    @field_validator("default_province")
    @classmethod
    def validate_province(cls, v: str) -> str:
        """Validate Canadian province/territory."""
        valid_provinces = {
            "BC", "AB", "SK", "MB", "ON", "QC", "NB", "NS", "PE", "NL",
            "YT", "NT", "NU"
        }
        if v not in valid_provinces:
            raise ValueError(f"Invalid province: {v}. Must be one of {valid_provinces}")
        return v

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v: str) -> str:
        """Validate business entity type."""
        valid_types = {
            "sole_proprietorship",  # Current support
            "corporation",  # Future support
            "partnership"   # Future support
        }
        if v not in valid_types:
            raise ValueError(f"Invalid entity type: {v}. Must be one of {valid_types}")
        # Currently only support sole proprietorship
        if v != "sole_proprietorship":
            raise ValueError(f"Entity type '{v}' not yet supported. Currently only 'sole_proprietorship' is supported.")
        return v

    @field_validator("business_type")
    @classmethod
    def validate_business_type(cls, v: str) -> str:
        """Validate business type."""
        valid_types = {
            "consulting", "retail", "professional_services", "technology",
            "healthcare", "construction", "manufacturing", "other"
        }
        if v not in valid_types:
            raise ValueError(f"Invalid business type: {v}. Must be one of {valid_types}")
        return v

    @field_validator("gst_number")
    @classmethod
    def validate_gst_number(cls, v: str | None) -> str | None:
        """Validate GST registration number format."""
        if v and not re.match(r'^\d{9}RT\d{4}$', v):
            raise ValueError('Invalid GST number format (expected: 123456789RT0001)')
        return v

class ProcessingConfiguration(BaseModel):
    """Processing preferences."""

    default_output_format: str = "human"  # human, json, csv
    auto_dry_run: bool = False  # For new users
    batch_continue_on_error: bool = True
    parallel_processing: bool = False
    parallel_workers: int = 1

    @field_validator("default_output_format")
    @classmethod
    def validate_output_format(cls, v: str) -> str:
        """Validate output format."""
        if v not in {"human", "json", "csv"}:
            raise ValueError("Output format must be 'human', 'json', or 'csv'")
        return v

class SystemConfiguration(BaseModel):
    """System-level configuration."""

    log_level: str = "INFO"
    checkpoint_retention_days: int = 7
    audit_log_retention_years: int = 7
    auto_cleanup_enabled: bool = True
    gemini_timeout_seconds: int = 30
```

### CLI Configuration Commands
```python
class ConfigCommands:
    """CLI commands for configuration management."""

    def __init__(self, config_manager: ConfigurationManager):
        self.config_manager = config_manager

    def show_config(self, section: str | None = None) -> None:
        """Show current configuration."""

        config = self.config_manager.load_configuration()

        if section:
            # Show specific section
            if section == "business":
                self._show_business_config(config.business)
            elif section == "processing":
                self._show_processing_config(config.processing)
            elif section == "system":
                self._show_system_config(config.system)
            else:
                print(f"Unknown configuration section: {section}")
        else:
            # Show all configuration
            self._show_all_config(config)

    def set_config(self, key: str, value: str) -> None:
        """Set configuration value."""

        try:
            # Convert string values to appropriate types
            converted_value = self._convert_value(key, value)
            self.config_manager.update_setting(key, converted_value)
            print(f"✅ Set {key} = {converted_value}")

        except Exception as e:
            print(f"❌ Failed to set {key}: {e}")

    def reset_config(self, confirm: bool = False) -> None:
        """Reset configuration to defaults."""

        if not confirm:
            response = input("Reset all configuration to defaults? (y/N): ")
            if response.lower() != 'y':
                print("Configuration reset cancelled")
                return

        default_config = UserConfiguration()
        self.config_manager.save_configuration(default_config)
        print("✅ Configuration reset to defaults")

    def validate_config(self) -> None:
        """Validate current configuration."""

        try:
            config = self.config_manager.load_configuration()
            print("✅ Configuration is valid")

            # Check for potential issues
            warnings = []

            if config.business.default_province != "BC":
                warnings.append(f"Default province is {config.business.default_province}, "
                               "ensure provincial tax rules are appropriate")

            if config.business.business_name is None:
                warnings.append("Business name not set - consider setting for better record keeping")

            if warnings:
                print("\n⚠️  Configuration warnings:")
                for warning in warnings:
                    print(f"  • {warning}")

        except Exception as e:
            print(f"❌ Configuration validation failed: {e}")
```

### CLI Integration
```bash
# Configuration management commands
quickexpense config show
quickexpense config show business
quickexpense config show processing

# Set configuration values
quickexpense config set business.default_province BC
quickexpense config set business.business_type consulting
quickexpense config set business.default_payment_method credit_card
quickexpense config set processing.default_output_format human

# Validate and reset
quickexpense config validate
quickexpense config reset

# Business context setup wizard
quickexpense config setup
```

### Enhanced Processing Integration
```python
class EnhancedExpenseProcessor:
    """Expense processor with automatic configuration application."""

    def __init__(self, config_manager: ConfigurationManager):
        self.config_manager = config_manager
        # ... other dependencies

    async def process_receipt_with_config(
        self,
        file_path: str,
        override_context: dict | None = None,
        dry_run: bool | None = None
    ) -> ProcessingResult:
        """Process receipt with automatic configuration application."""

        # Get default business context
        business_context = self.config_manager.get_business_context()

        # Apply overrides if provided
        if override_context:
            for key, value in override_context.items():
                setattr(business_context, key, value)

        # Get processing preferences
        config = self.config_manager.load_configuration()

        # Use configured dry-run preference if not specified
        if dry_run is None:
            dry_run = config.processing.auto_dry_run

        # Process with applied context
        return await self.process_receipt(
            file_path=file_path,
            business_context=business_context,
            dry_run=dry_run
        )
```

## Testing Requirements

### Unit Tests
- [ ] Test configuration loading and saving
- [ ] Test configuration validation and migration
- [ ] Test CLI configuration commands
- [ ] Test business context application
- [ ] Test configuration override mechanisms

### Integration Tests
- [ ] Test end-to-end processing with configuration
- [ ] Test configuration persistence across sessions
- [ ] Test configuration migration scenarios
- [ ] Test invalid configuration handling

## Dependencies
- Existing CLI interface ✅ Completed
- Core settings system ✅ Completed
- Business context integration (existing processors)

## Definition of Done
- [ ] Configuration storage and management system
- [ ] CLI commands for configuration management
- [ ] Automatic application of business context
- [ ] Configuration validation and migration
- [ ] Override capability for per-receipt customization
- [ ] Unit tests pass with >95% coverage
- [ ] Integration tests validate configuration workflows
- [ ] User experience is intuitive and helpful
- [ ] Pre-commit hooks pass (ruff, mypy, pyright, black)

## Validation Scenarios

### Scenario 1: First-Time User Setup
**Given** new user running system for first time
**When** processing their first receipt
**Then**
- Default configuration created automatically
- BC province and consulting business type applied
- User prompted to run `quickexpense config setup` for customization
- Processing succeeds with reasonable defaults

### Scenario 2: Business Context Configuration
**Given** user setting up business configuration
**When** running configuration commands
**Then**
```bash
$ quickexpense config set business.default_province ON
✅ Set business.default_province = ON

$ quickexpense config set business.business_type retail
✅ Set business.business_type = retail

$ quickexpense config show business
Business Configuration:
  Province: ON (13% HST)
  Business Type: retail
  Default Payment: credit_card
  Currency: CAD
```

### Scenario 3: Automatic Application with Override
**Given** user with configured defaults (province=BC, type=consulting)
**When** processing receipt with override context
**Then**
```bash
# Uses configured defaults
$ quickexpense upload receipt.pdf
Province: BC (configured default)
Business Type: consulting

# Override for specific receipt
$ quickexpense upload receipt.pdf --province ON --business-type retail
Province: ON (override)
Business Type: retail (override)
```

## Risk Mitigation
- **Configuration Corruption:** Atomic writes and validation
- **Migration Issues:** Careful version handling and fallbacks
- **User Experience:** Clear error messages and helpful defaults
- **Data Privacy:** Local configuration storage only

## Success Metrics
- 90% reduction in repetitive data entry
- Zero configuration-related processing failures
- 100% successful configuration migration across versions
- User satisfaction >4.5/5 for configuration experience
- <30 seconds for complete business context setup
