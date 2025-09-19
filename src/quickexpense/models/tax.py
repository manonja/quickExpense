"""Tax models for Canadian provincial tax calculations."""

from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field

from .t2125 import T2125LineItem


class ProvinceCode(str, Enum):
    """Canadian province and territory codes."""

    BC = "BC"  # British Columbia
    AB = "AB"  # Alberta
    SK = "SK"  # Saskatchewan
    MB = "MB"  # Manitoba
    ON = "ON"  # Ontario
    QC = "QC"  # Quebec
    NB = "NB"  # New Brunswick
    NS = "NS"  # Nova Scotia
    PE = "PE"  # Prince Edward Island
    NL = "NL"  # Newfoundland and Labrador
    YT = "YT"  # Yukon
    NT = "NT"  # Northwest Territories
    NU = "NU"  # Nunavut


class TaxType(str, Enum):
    """Types of Canadian taxes."""

    GST = "GST"  # Goods and Services Tax
    HST = "HST"  # Harmonized Sales Tax
    PST = "PST"  # Provincial Sales Tax
    QST = "QST"  # Quebec Sales Tax


class ProvinceDetection(BaseModel):
    """Province detection result from address parsing."""

    province: ProvinceCode
    confidence: float = Field(..., ge=0.0, le=1.0)
    detection_method: str  # "address", "postal_code", "default"
    vendor_address: str | None = None
    postal_code: str | None = None


class TaxBreakdown(BaseModel):
    """Detailed provincial tax breakdown."""

    province: ProvinceCode
    total_amount: Decimal = Field(..., decimal_places=2)
    tax_amount: Decimal = Field(..., decimal_places=2)

    # Individual tax components
    gst_amount: Decimal = Field(default=Decimal("0.00"), decimal_places=2)
    pst_amount: Decimal = Field(default=Decimal("0.00"), decimal_places=2)
    hst_amount: Decimal = Field(default=Decimal("0.00"), decimal_places=2)
    qst_amount: Decimal = Field(default=Decimal("0.00"), decimal_places=2)

    # Tax rates used
    gst_rate: Decimal = Field(default=Decimal("0.00"), decimal_places=4)
    pst_rate: Decimal = Field(default=Decimal("0.00"), decimal_places=4)
    hst_rate: Decimal = Field(default=Decimal("0.00"), decimal_places=4)
    qst_rate: Decimal = Field(default=Decimal("0.00"), decimal_places=4)

    @property
    def tax_type(self) -> str:
        """Get the tax type description for this province."""
        if self.hst_amount > 0:
            return "HST"
        if self.gst_amount > 0 and self.qst_amount > 0:
            return "GST+QST"
        if self.gst_amount > 0 and self.pst_amount > 0:
            return "GST+PST"
        if self.gst_amount > 0:
            return "GST"
        return "Unknown"


class InputTaxCredits(BaseModel):
    """Input Tax Credit calculations by tax type."""

    total_itc: Decimal = Field(default=Decimal("0.00"), decimal_places=2)
    gst_itc: Decimal = Field(default=Decimal("0.00"), decimal_places=2)
    hst_itc: Decimal = Field(default=Decimal("0.00"), decimal_places=2)
    qst_itc: Decimal = Field(default=Decimal("0.00"), decimal_places=2)
    pst_itc: Decimal = Field(default=Decimal("0.00"), decimal_places=2)  # Usually 0

    @property
    def has_itc_eligible_taxes(self) -> bool:
        """Check if there are any ITC-eligible taxes."""
        return self.total_itc > 0


class EntityAwareExpenseMapping(BaseModel):
    """Entity-aware expense mapping to tax forms."""

    entity_type: str
    expense_category: str
    form_line_item: str
    form_line_description: str
    deductibility_percentage: float = Field(..., ge=0.0, le=100.0)
    ita_reference: str | None = None

    @classmethod
    def get_mapping(
        cls, entity_type: str, category: str
    ) -> "EntityAwareExpenseMapping":
        """Get expense mapping based on entity type."""

        if entity_type == "sole_proprietorship":
            # Map to T2125 line items
            line_item = T2125LineItem.from_category(category)

            return cls(
                entity_type="sole_proprietorship",
                expense_category=category,
                form_line_item=line_item.value,
                form_line_description=line_item.description,
                deductibility_percentage=line_item.deductibility_percentage,
                ita_reference=line_item.ita_reference,
            )

        # Future: Corporation (T2) and Partnership (T5013) mappings
        if entity_type == "corporation":
            raise NotImplementedError("Corporation entity type not yet implemented")
        if entity_type == "partnership":
            raise NotImplementedError("Partnership entity type not yet implemented")
        raise ValueError(f"Unsupported entity type: {entity_type}")


class ProvincialTaxConfig(BaseModel):
    """Provincial tax configuration."""

    province: ProvinceCode
    gst_rate: Decimal = Field(default=Decimal("0.05"), decimal_places=5)
    pst_rate: Decimal = Field(default=Decimal("0.00"), decimal_places=5)
    hst_rate: Decimal = Field(default=Decimal("0.00"), decimal_places=5)
    qst_rate: Decimal = Field(default=Decimal("0.00"), decimal_places=5)

    # ITC eligibility
    gst_itc_eligible: bool = True
    pst_itc_eligible: bool = False
    hst_itc_eligible: bool = True
    qst_itc_eligible: bool = True

    @property
    def combined_rate(self) -> Decimal:
        """Get the combined tax rate for this province."""
        return self.gst_rate + self.pst_rate + self.hst_rate + self.qst_rate

    @property
    def tax_type_description(self) -> str:
        """Get human-readable tax type description."""
        if self.hst_rate > 0:
            return f"HST ({self.hst_rate * 100:.1f}%)"
        if self.gst_rate > 0 and self.qst_rate > 0:
            return (
                f"GST ({self.gst_rate * 100:.1f}%) + QST ({self.qst_rate * 100:.3f}%)"
            )
        if self.gst_rate > 0 and self.pst_rate > 0:
            return (
                f"GST ({self.gst_rate * 100:.1f}%) + PST ({self.pst_rate * 100:.1f}%)"
            )
        if self.gst_rate > 0:
            return f"GST ({self.gst_rate * 100:.1f}%)"
        return "No applicable taxes"


# Provincial tax configuration data
PROVINCIAL_TAX_RATES: dict[ProvinceCode, ProvincialTaxConfig] = {
    ProvinceCode.BC: ProvincialTaxConfig(
        province=ProvinceCode.BC,
        gst_rate=Decimal("0.05"),
        pst_rate=Decimal("0.07"),
        pst_itc_eligible=False,
    ),
    ProvinceCode.AB: ProvincialTaxConfig(
        province=ProvinceCode.AB, gst_rate=Decimal("0.05")
    ),
    ProvinceCode.SK: ProvincialTaxConfig(
        province=ProvinceCode.SK,
        gst_rate=Decimal("0.05"),
        pst_rate=Decimal("0.06"),
        pst_itc_eligible=False,
    ),
    ProvinceCode.MB: ProvincialTaxConfig(
        province=ProvinceCode.MB,
        gst_rate=Decimal("0.05"),
        pst_rate=Decimal("0.07"),
        pst_itc_eligible=False,
    ),
    ProvinceCode.ON: ProvincialTaxConfig(
        province=ProvinceCode.ON,
        hst_rate=Decimal("0.13"),
        gst_rate=Decimal("0.00"),  # GST is included in HST
        hst_itc_eligible=True,
    ),
    ProvinceCode.QC: ProvincialTaxConfig(
        province=ProvinceCode.QC,
        gst_rate=Decimal("0.05"),
        qst_rate=Decimal("0.09975"),
        qst_itc_eligible=True,
    ),
    ProvinceCode.NB: ProvincialTaxConfig(
        province=ProvinceCode.NB,
        hst_rate=Decimal("0.15"),
        gst_rate=Decimal("0.00"),  # GST is included in HST
        hst_itc_eligible=True,
    ),
    ProvinceCode.NS: ProvincialTaxConfig(
        province=ProvinceCode.NS,
        hst_rate=Decimal("0.15"),
        gst_rate=Decimal("0.00"),  # GST is included in HST
        hst_itc_eligible=True,
    ),
    ProvinceCode.PE: ProvincialTaxConfig(
        province=ProvinceCode.PE,
        hst_rate=Decimal("0.15"),
        gst_rate=Decimal("0.00"),  # GST is included in HST
        hst_itc_eligible=True,
    ),
    ProvinceCode.NL: ProvincialTaxConfig(
        province=ProvinceCode.NL,
        hst_rate=Decimal("0.15"),
        gst_rate=Decimal("0.00"),  # GST is included in HST
        hst_itc_eligible=True,
    ),
    ProvinceCode.YT: ProvincialTaxConfig(
        province=ProvinceCode.YT, gst_rate=Decimal("0.05")
    ),
    ProvinceCode.NT: ProvincialTaxConfig(
        province=ProvinceCode.NT, gst_rate=Decimal("0.05")
    ),
    ProvinceCode.NU: ProvincialTaxConfig(
        province=ProvinceCode.NU, gst_rate=Decimal("0.05")
    ),
}
