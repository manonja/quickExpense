"""Provincial tax service for Canadian tax calculations."""

import re
from decimal import Decimal
from typing import ClassVar

from quickexpense.models.tax import (
    PROVINCIAL_TAX_RATES,
    InputTaxCredits,
    ProvinceCode,
    ProvinceDetection,
    ProvincialTaxConfig,
    TaxBreakdown,
)


class ProvincialTaxService:
    """Handle provincial tax rates and calculations across Canada."""

    # Postal code patterns for province detection
    POSTAL_CODE_PATTERNS: ClassVar[dict[ProvinceCode, list[str]]] = {
        ProvinceCode.BC: [r"^V\d[A-Z]\s?\d[A-Z]\d$"],
        ProvinceCode.AB: [r"^T\d[A-Z]\s?\d[A-Z]\d$"],
        ProvinceCode.SK: [r"^S\d[A-Z]\s?\d[A-Z]\d$"],
        ProvinceCode.MB: [r"^R\d[A-Z]\s?\d[A-Z]\d$"],
        ProvinceCode.ON: [r"^[KLMNP]\d[A-Z]\s?\d[A-Z]\d$"],
        ProvinceCode.QC: [r"^[GHJ]\d[A-Z]\s?\d[A-Z]\d$"],
        ProvinceCode.NB: [r"^E\d[A-Z]\s?\d[A-Z]\d$"],
        ProvinceCode.NS: [r"^B\d[A-Z]\s?\d[A-Z]\d$"],
        ProvinceCode.PE: [r"^C\d[A-Z]\s?\d[A-Z]\d$"],
        ProvinceCode.NL: [r"^A\d[A-Z]\s?\d[A-Z]\d$"],
        ProvinceCode.YT: [r"^Y\d[A-Z]\s?\d[A-Z]\d$"],
        ProvinceCode.NT: [r"^X\d[A-Z]\s?\d[A-Z]\d$"],
        ProvinceCode.NU: [r"^X\d[A-Z]\s?\d[A-Z]\d$"],  # Same as NT
    }

    # Common province name variations for address parsing
    PROVINCE_NAMES: ClassVar[dict[ProvinceCode, list[str]]] = {
        ProvinceCode.BC: ["british columbia", "bc", "b.c."],
        ProvinceCode.AB: ["alberta", "ab", "alta"],
        ProvinceCode.SK: ["saskatchewan", "sk", "sask"],
        ProvinceCode.MB: ["manitoba", "mb", "man"],
        ProvinceCode.ON: ["ontario", "on", "ont"],
        ProvinceCode.QC: ["quebec", "qc", "que", "québec"],
        ProvinceCode.NB: ["new brunswick", "nb", "n.b."],
        ProvinceCode.NS: ["nova scotia", "ns", "n.s."],
        ProvinceCode.PE: ["prince edward island", "pe", "p.e.i.", "pei"],
        ProvinceCode.NL: ["newfoundland and labrador", "nl", "n.l.", "newfoundland"],
        ProvinceCode.YT: ["yukon", "yt", "y.t."],
        ProvinceCode.NT: ["northwest territories", "nt", "n.w.t.", "nwt"],
        ProvinceCode.NU: ["nunavut", "nu"],
    }

    def __init__(self, default_province: ProvinceCode = ProvinceCode.BC) -> None:
        """Initialize with a default province for fallback."""
        self.default_province = default_province

    def detect_province(
        self, vendor_address: str | None = None, postal_code: str | None = None
    ) -> ProvinceDetection:
        """Auto-detect province from address information."""

        # Try postal code first (most reliable)
        if postal_code:
            province = self._detect_from_postal_code(postal_code)
            if province:
                return ProvinceDetection(
                    province=province,
                    confidence=0.95,
                    detection_method="postal_code",
                    vendor_address=vendor_address,
                    postal_code=postal_code,
                )

        # Try address text parsing
        if vendor_address:
            province = self._detect_from_address(vendor_address)
            if province:
                return ProvinceDetection(
                    province=province,
                    confidence=0.80,
                    detection_method="address",
                    vendor_address=vendor_address,
                    postal_code=postal_code,
                )

        # Fallback to default province
        return ProvinceDetection(
            province=self.default_province,
            confidence=0.50,
            detection_method="default",
            vendor_address=vendor_address,
            postal_code=postal_code,
        )

    def _detect_from_postal_code(self, postal_code: str) -> ProvinceCode | None:
        """Detect province from Canadian postal code."""
        # Clean postal code
        clean_postal = postal_code.upper().replace(" ", "")

        for province, patterns in self.POSTAL_CODE_PATTERNS.items():
            for pattern in patterns:
                if re.match(pattern, clean_postal):
                    return province

        return None

    def _detect_from_address(self, address: str) -> ProvinceCode | None:
        """Detect province from address text."""
        address_lower = address.lower()

        for province, names in self.PROVINCE_NAMES.items():
            for name in names:
                if name in address_lower:
                    return province

        return None

    def calculate_tax_breakdown(
        self, total_amount: Decimal, tax_amount: Decimal, province: ProvinceCode
    ) -> TaxBreakdown:
        """Calculate detailed tax breakdown by province."""

        config = PROVINCIAL_TAX_RATES.get(province)
        if not config:
            raise ValueError(f"Unsupported province: {province}")

        # Calculate base amount (pre-tax)
        base_amount = total_amount - tax_amount

        breakdown = TaxBreakdown(
            province=province, total_amount=total_amount, tax_amount=tax_amount
        )

        # Calculate individual tax components based on province type
        if config.hst_rate > 0:
            # HST province (ON, NB, NS, PE, NL)
            breakdown.hst_amount = tax_amount
            breakdown.hst_rate = config.hst_rate
        elif config.gst_rate > 0 and config.qst_rate > 0:
            # Quebec: GST + QST, QST is calculated on price including GST
            gst_amount = base_amount * config.gst_rate
            qst_amount = tax_amount - gst_amount

            breakdown.gst_amount = gst_amount
            breakdown.qst_amount = qst_amount
            breakdown.gst_rate = config.gst_rate
            breakdown.qst_rate = config.qst_rate
        elif config.gst_rate > 0 and config.pst_rate > 0:
            # GST + PST provinces (BC, SK, MB)
            gst_amount = base_amount * config.gst_rate
            pst_amount = base_amount * config.pst_rate

            breakdown.gst_amount = gst_amount
            breakdown.pst_amount = pst_amount
            breakdown.gst_rate = config.gst_rate
            breakdown.pst_rate = config.pst_rate
        elif config.gst_rate > 0:
            # GST only (AB, YT, NT, NU)
            breakdown.gst_amount = tax_amount
            breakdown.gst_rate = config.gst_rate

        return breakdown

    def calculate_input_tax_credits(
        self, tax_breakdown: TaxBreakdown, *, gst_registered: bool = True
    ) -> InputTaxCredits:
        """Calculate Input Tax Credits based on provincial rules."""

        if not gst_registered:
            # Not GST registered, no ITCs available
            return InputTaxCredits()

        config = PROVINCIAL_TAX_RATES.get(tax_breakdown.province)
        if not config:
            raise ValueError(f"Unsupported province: {tax_breakdown.province}")

        itc = InputTaxCredits()

        # Calculate ITCs based on eligibility
        if config.gst_itc_eligible and tax_breakdown.gst_amount > 0:
            itc.gst_itc = tax_breakdown.gst_amount

        if config.hst_itc_eligible and tax_breakdown.hst_amount > 0:
            itc.hst_itc = tax_breakdown.hst_amount

        if config.qst_itc_eligible and tax_breakdown.qst_amount > 0:
            itc.qst_itc = tax_breakdown.qst_amount

        if config.pst_itc_eligible and tax_breakdown.pst_amount > 0:
            itc.pst_itc = tax_breakdown.pst_amount

        # Calculate total ITC
        itc.total_itc = itc.gst_itc + itc.hst_itc + itc.qst_itc + itc.pst_itc

        return itc

    def get_provincial_config(self, province: ProvinceCode) -> ProvincialTaxConfig:
        """Get tax configuration for a province."""
        config = PROVINCIAL_TAX_RATES.get(province)
        if not config:
            raise ValueError(f"Unsupported province: {province}")
        return config

    def validate_tax_amount(
        self,
        base_amount: Decimal,
        actual_tax: Decimal,
        province: ProvinceCode,
        tolerance: Decimal = Decimal("0.05"),
    ) -> bool:
        """Validate if tax amount is reasonable for the province."""

        config = self.get_provincial_config(province)
        expected_tax = base_amount * config.combined_rate

        # Allow for rounding differences
        difference = abs(actual_tax - expected_tax)
        return difference <= tolerance

    def get_all_provinces(self) -> list[ProvinceCode]:
        """Get list of all supported provinces."""
        return list(PROVINCIAL_TAX_RATES.keys())

    def format_tax_summary(
        self, tax_breakdown: TaxBreakdown, itc: InputTaxCredits
    ) -> str:
        """Format a human-readable tax summary."""
        lines = [
            f"Province: {tax_breakdown.province.value}",
            f"Tax Type: {tax_breakdown.tax_type}",
            f"Total Tax: ${tax_breakdown.tax_amount:.2f}",
        ]

        # Add breakdown details
        if tax_breakdown.hst_amount > 0:
            hst_line = (
                f"HST ({tax_breakdown.hst_rate * 100:.1f}%): "
                f"${tax_breakdown.hst_amount:.2f}"
            )
            lines.append(hst_line)
        if tax_breakdown.gst_amount > 0:
            gst_line = (
                f"GST ({tax_breakdown.gst_rate * 100:.1f}%): "
                f"${tax_breakdown.gst_amount:.2f}"
            )
            lines.append(gst_line)
        if tax_breakdown.pst_amount > 0:
            pst_line = (
                f"PST ({tax_breakdown.pst_rate * 100:.1f}%): "
                f"${tax_breakdown.pst_amount:.2f}"
            )
            lines.append(pst_line)
        if tax_breakdown.qst_amount > 0:
            qst_line = (
                f"QST ({tax_breakdown.qst_rate * 100:.3f}%): "
                f"${tax_breakdown.qst_amount:.2f}"
            )
            lines.append(qst_line)

        # Add ITC information
        if itc.total_itc > 0:
            lines.append(f"Input Tax Credit: ${itc.total_itc:.2f}")

        return "\n".join(lines)
