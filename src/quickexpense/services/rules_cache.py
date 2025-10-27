"""Business rules cache service for startup loading and hot-reload."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from quickexpense.services.business_rules import BusinessRuleEngine
from quickexpense.services.cra_business_rules import CRABusinessRulesService

if TYPE_CHECKING:
    from quickexpense.core.config import Settings

logger = logging.getLogger(__name__)


class RulesCacheService:
    """Service for caching business rules at application startup."""

    def __init__(self, settings: Settings) -> None:
        """Initialize the rules cache service.

        Args:
            settings: Application settings
        """
        self.settings = settings
        self.business_rule_engine: BusinessRuleEngine | None = None
        self.cra_rules_service: CRABusinessRulesService | None = None
        self._is_loaded = False

    def load_rules(self) -> None:
        """Load all business rules into memory."""
        if not self.settings.enable_business_rules_cache:
            logger.info("Business rules caching is disabled")
            return

        logger.info("Loading business rules into cache...")

        try:
            # Load JSON-based business rules
            rules_config_path = Path(self.settings.business_rules_config_path)
            if not rules_config_path.is_absolute():
                # Resolve relative to project root
                base_path = Path(__file__).parent.parent.parent.parent
                rules_config_path = base_path / rules_config_path

            self.business_rule_engine = BusinessRuleEngine(
                config_path=rules_config_path,
                entity_type="sole_proprietorship",
            )

            logger.info(
                "Loaded %d business rules from %s",
                (
                    len(self.business_rule_engine.config.rules)
                    if self.business_rule_engine.config
                    else 0
                ),
                rules_config_path,
            )

            # Load CSV-based CRA rules
            cra_rules_path = Path(self.settings.cra_rules_csv_path)
            if not cra_rules_path.is_absolute():
                base_path = Path(__file__).parent.parent.parent.parent
                cra_rules_path = base_path / cra_rules_path

            self.cra_rules_service = CRABusinessRulesService(
                rules_csv_path=cra_rules_path
            )

            logger.info(
                "Loaded %d CRA business rules from %s",
                len(self.cra_rules_service.rules),
                cra_rules_path,
            )

            self._is_loaded = True
            logger.info("Business rules cache loaded successfully")

        except Exception:
            logger.exception("Failed to load business rules cache")
            # Set to None to force lazy loading on first use
            self.business_rule_engine = None
            self.cra_rules_service = None
            self._is_loaded = False

    def reload_rules(self) -> dict[str, int]:
        """Hot-reload business rules from configuration files.

        Returns:
            Dictionary with rule counts after reload
        """
        logger.info("Hot-reloading business rules...")

        try:
            if self.business_rule_engine:
                old_count = (
                    len(self.business_rule_engine.config.rules)
                    if self.business_rule_engine.config
                    else 0
                )
                self.business_rule_engine.reload_rules()
                new_count = (
                    len(self.business_rule_engine.config.rules)
                    if self.business_rule_engine.config
                    else 0
                )
                logger.info(
                    "Business rules reloaded: %d rules (was %d)", new_count, old_count
                )
            else:
                # Load for the first time if not already loaded
                self.load_rules()

            if self.cra_rules_service:
                old_cra_count = len(self.cra_rules_service.rules)
                self.cra_rules_service.reload_rules()
                new_cra_count = len(self.cra_rules_service.rules)
                logger.info(
                    "CRA rules reloaded: %d rules (was %d)",
                    new_cra_count,
                    old_cra_count,
                )

            return {
                "business_rules_count": (
                    len(self.business_rule_engine.config.rules)
                    if self.business_rule_engine and self.business_rule_engine.config
                    else 0
                ),
                "cra_rules_count": (
                    len(self.cra_rules_service.rules) if self.cra_rules_service else 0
                ),
            }

        except Exception:
            logger.exception("Failed to reload business rules")
            raise

    def get_business_rule_engine(self) -> BusinessRuleEngine:
        """Get the cached business rule engine.

        Returns:
            Business rule engine instance

        Raises:
            RuntimeError: If rules are not loaded and lazy loading fails
        """
        if not self.business_rule_engine:
            if not self._is_loaded:
                # Lazy load if not already loaded
                msg = (
                    "Business rules not cached, "
                    "performing lazy load (performance penalty)"
                )
                logger.warning(msg)
                self.load_rules()

            if not self.business_rule_engine:
                msg = "Business rules engine not available"
                raise RuntimeError(msg)

        return self.business_rule_engine

    def get_cra_rules_service(self) -> CRABusinessRulesService:
        """Get the cached CRA rules service.

        Returns:
            CRA rules service instance

        Raises:
            RuntimeError: If rules are not loaded and lazy loading fails
        """
        if not self.cra_rules_service:
            if not self._is_loaded:
                # Lazy load if not already loaded
                logger.warning(
                    "CRA rules not cached, performing lazy load (performance penalty)"
                )
                self.load_rules()

            if not self.cra_rules_service:
                msg = "CRA rules service not available"
                raise RuntimeError(msg)

        return self.cra_rules_service

    @property
    def is_loaded(self) -> bool:
        """Check if rules are loaded into cache."""
        return self._is_loaded

    def get_cache_status(self) -> dict[str, bool | int]:
        """Get cache status information.

        Returns:
            Dictionary with cache status details
        """
        return {
            "enabled": self.settings.enable_business_rules_cache,
            "loaded": self._is_loaded,
            "business_rules_loaded": self.business_rule_engine is not None,
            "business_rules_count": (
                len(self.business_rule_engine.config.rules)
                if self.business_rule_engine and self.business_rule_engine.config
                else 0
            ),
            "cra_rules_loaded": self.cra_rules_service is not None,
            "cra_rules_count": (
                len(self.cra_rules_service.rules) if self.cra_rules_service else 0
            ),
        }
