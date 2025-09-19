"""T2125 form models for Canadian sole proprietorship tax compliance."""

from enum import Enum


class T2125LineItem(str, Enum):
    """Official T2125 form line items for sole proprietors.

    These correspond to the official Canada Revenue Agency (CRA) T2125 form:
    Statement of Business or Professional Activities.
    """

    # Income lines
    GROSS_SALES = "8000"

    # Expense lines
    ADVERTISING = "8521"
    MEALS_ENTERTAINMENT = "8523"  # 50% deductible per ITA Section 67.1
    BAD_DEBTS = "8590"
    INTEREST = "8710"
    BUSINESS_TAX = "8760"
    LICENCES = "8764"
    OFFICE_SUPPLIES = "8811"
    PROFESSIONAL_FEES = "8860"
    MANAGEMENT_FEES = "8871"
    TRAVEL = "8890"
    RENT = "8910"
    MAINTENANCE = "8960"
    SALARIES_WAGES = "9060"
    SUBCONTRACTS = "9180"
    TELEPHONE = "9220"
    UTILITIES = "9270"
    VEHICLE_EXPENSES = "9281"
    HOME_OFFICE = "9945"
    OTHER_EXPENSES = "9999"

    @property
    def description(self) -> str:
        """Get human-readable description of line item."""
        descriptions = {
            "8000": "Gross sales",
            "8521": "Advertising",
            "8523": "Meals and entertainment",
            "8590": "Bad debts",
            "8710": "Interest",
            "8760": "Business tax, fees, licences",
            "8764": "Licences",
            "8811": "Office expenses",
            "8860": "Professional fees",
            "8871": "Management and administration fees",
            "8890": "Travel",
            "8910": "Rent",
            "8960": "Maintenance and repairs",
            "9060": "Salaries, wages, and benefits",
            "9180": "Subcontracts",
            "9220": "Telephone and utilities",
            "9270": "Utilities",
            "9281": "Motor vehicle expenses",
            "9945": "Business-use-of-home expenses",
            "9999": "Other expenses",
        }
        return descriptions.get(self.value, self.value)

    @property
    def deductibility_percentage(self) -> float:
        """Get default deductibility percentage for this line item."""
        # Most expenses are 100% deductible
        # Meals and entertainment are limited to 50% per ITA Section 67.1
        if self == T2125LineItem.MEALS_ENTERTAINMENT:
            return 50.0
        return 100.0

    @property
    def ita_reference(self) -> str | None:
        """Get Income Tax Act reference for special rules."""
        if self == T2125LineItem.MEALS_ENTERTAINMENT:
            return "ITA Section 67.1"
        if self == T2125LineItem.HOME_OFFICE:
            return "ITA Section 18(12)"
        return None

    @classmethod
    def from_category(cls, expense_category: str) -> "T2125LineItem":
        """Map expense category to T2125 line item."""
        category_mappings = {
            "Travel-Meals": cls.MEALS_ENTERTAINMENT,
            "Travel-Lodging": cls.TRAVEL,
            "Travel-Transportation": cls.TRAVEL,
            "Office-Supplies": cls.OFFICE_SUPPLIES,
            "Professional-Services": cls.PROFESSIONAL_FEES,
            "Professional-Legal": cls.PROFESSIONAL_FEES,
            "Professional-Accounting": cls.PROFESSIONAL_FEES,
            "Marketing-Advertising": cls.ADVERTISING,
            "Vehicle-Gas": cls.VEHICLE_EXPENSES,
            "Vehicle-Maintenance": cls.VEHICLE_EXPENSES,
            "Communications-Phone": cls.TELEPHONE,
            "Communications-Internet": cls.TELEPHONE,
            "Rent-Office": cls.RENT,
            "Utilities-Electric": cls.UTILITIES,
            "Utilities-Gas": cls.UTILITIES,
            "Home-Office": cls.HOME_OFFICE,
        }
        return category_mappings.get(expense_category, cls.OTHER_EXPENSES)


def get_t2125_mapping() -> dict[str, dict[str, str | float | None]]:
    """Get complete T2125 mapping for business categories."""
    return {
        category: {
            "line_item": T2125LineItem.from_category(category).value,
            "description": T2125LineItem.from_category(category).description,
            "deductibility": T2125LineItem.from_category(
                category
            ).deductibility_percentage,
            "ita_reference": T2125LineItem.from_category(category).ita_reference,
        }
        for category in [
            "Travel-Meals",
            "Travel-Lodging",
            "Travel-Transportation",
            "Office-Supplies",
            "Professional-Services",
            "Professional-Legal",
            "Professional-Accounting",
            "Marketing-Advertising",
            "Vehicle-Gas",
            "Vehicle-Maintenance",
            "Communications-Phone",
            "Communications-Internet",
            "Rent-Office",
            "Utilities-Electric",
            "Utilities-Gas",
            "Home-Office",
        ]
    }
