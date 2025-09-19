"""Tests for provincial tax service."""

from decimal import Decimal

import pytest

from quickexpense.models.tax import (
    InputTaxCredits,
    ProvinceCode,
    TaxBreakdown,
)
from quickexpense.services.provincial_tax import ProvincialTaxService


class TestProvincialTaxService:
    """Test provincial tax service functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = ProvincialTaxService(default_province=ProvinceCode.BC)

    def test_detect_province_from_postal_code(self):
        """Test province detection from postal codes."""
        test_cases = [
            ("V6B 2W9", ProvinceCode.BC, 0.95),
            ("T2P 1J9", ProvinceCode.AB, 0.95),
            ("S4P 3Y2", ProvinceCode.SK, 0.95),
            ("R3C 4W2", ProvinceCode.MB, 0.95),
            ("M5V 3M6", ProvinceCode.ON, 0.95),
            ("H3A 0G4", ProvinceCode.QC, 0.95),
            ("E1C 8X9", ProvinceCode.NB, 0.95),
            ("B3H 2Y8", ProvinceCode.NS, 0.95),
            ("C1A 7M4", ProvinceCode.PE, 0.95),
            ("A1C 5X8", ProvinceCode.NL, 0.95),
            ("Y1A 6K1", ProvinceCode.YT, 0.95),
            ("X1A 2N2", ProvinceCode.NT, 0.95),
        ]

        for postal_code, expected_province, expected_confidence in test_cases:
            result = self.service.detect_province(postal_code=postal_code)
            assert result.province == expected_province
            assert result.confidence == expected_confidence
            assert result.detection_method == "postal_code"
            assert result.postal_code == postal_code

    def test_detect_province_from_address(self):
        """Test province detection from address text."""
        test_cases = [
            ("123 Main St, Vancouver, BC", ProvinceCode.BC),
            ("456 1st Ave, Calgary, Alberta", ProvinceCode.AB),
            ("789 Broadway, Toronto, Ontario", ProvinceCode.ON),
            ("321 Rue St-Denis, Montreal, Quebec", ProvinceCode.QC),
            ("555 Water St, Halifax, Nova Scotia", ProvinceCode.NS),
        ]

        for address, expected_province in test_cases:
            result = self.service.detect_province(vendor_address=address)
            assert result.province == expected_province
            assert result.confidence == 0.80
            assert result.detection_method == "address"
            assert result.vendor_address == address

    def test_detect_province_fallback_to_default(self):
        """Test fallback to default province when detection fails."""
        result = self.service.detect_province(vendor_address="Unknown Address")
        assert result.province == ProvinceCode.BC
        assert result.confidence == 0.50
        assert result.detection_method == "default"

    def test_calculate_tax_breakdown_bc(self):
        """Test BC tax breakdown (GST + PST)."""
        total = Decimal("112.00")
        tax = Decimal("12.00")

        breakdown = self.service.calculate_tax_breakdown(total, tax, ProvinceCode.BC)

        assert breakdown.province == ProvinceCode.BC
        assert breakdown.total_amount == total
        assert breakdown.tax_amount == tax
        assert breakdown.gst_amount == Decimal("5.00")  # 5% of 100
        assert breakdown.pst_amount == Decimal("7.00")  # 7% of 100
        assert breakdown.tax_type == "GST+PST"

    def test_calculate_tax_breakdown_ontario(self):
        """Test Ontario HST tax breakdown."""
        total = Decimal("113.00")
        tax = Decimal("13.00")

        breakdown = self.service.calculate_tax_breakdown(total, tax, ProvinceCode.ON)

        assert breakdown.province == ProvinceCode.ON
        assert breakdown.total_amount == total
        assert breakdown.tax_amount == tax
        assert breakdown.hst_amount == tax
        assert breakdown.hst_rate == Decimal("0.13")
        assert breakdown.tax_type == "HST"

    def test_calculate_tax_breakdown_quebec(self):
        """Test Quebec tax breakdown (GST + QST)."""
        total = Decimal("114.98")
        tax = Decimal("14.98")
        base = Decimal("100.00")

        breakdown = self.service.calculate_tax_breakdown(total, tax, ProvinceCode.QC)

        assert breakdown.province == ProvinceCode.QC
        assert breakdown.total_amount == total
        assert breakdown.tax_amount == tax

        # GST is 5% of base
        expected_gst = base * Decimal("0.05")
        assert abs(breakdown.gst_amount - expected_gst) < Decimal("0.01")

        # QST is remainder
        expected_qst = tax - expected_gst
        assert abs(breakdown.qst_amount - expected_qst) < Decimal("0.01")
        assert breakdown.tax_type == "GST+QST"

    def test_calculate_tax_breakdown_alberta(self):
        """Test Alberta tax breakdown (GST only)."""
        total = Decimal("105.00")
        tax = Decimal("5.00")

        breakdown = self.service.calculate_tax_breakdown(total, tax, ProvinceCode.AB)

        assert breakdown.province == ProvinceCode.AB
        assert breakdown.total_amount == total
        assert breakdown.tax_amount == tax
        assert breakdown.gst_amount == tax
        assert breakdown.gst_rate == Decimal("0.05")
        assert breakdown.tax_type == "GST"

    def test_calculate_input_tax_credits_gst_registered(self):
        """Test ITC calculation for GST registered business."""
        # BC breakdown
        breakdown = TaxBreakdown(
            province=ProvinceCode.BC,
            total_amount=Decimal("112.00"),
            tax_amount=Decimal("12.00"),
            gst_amount=Decimal("5.00"),
            pst_amount=Decimal("7.00"),
            gst_rate=Decimal("0.05"),
            pst_rate=Decimal("0.07"),
        )

        itc = self.service.calculate_input_tax_credits(breakdown, gst_registered=True)

        # Only GST is ITC eligible, not PST
        assert itc.gst_itc == Decimal("5.00")
        assert itc.pst_itc == Decimal("0.00")
        assert itc.total_itc == Decimal("5.00")

    def test_calculate_input_tax_credits_not_registered(self):
        """Test ITC calculation for non-GST registered business."""
        breakdown = TaxBreakdown(
            province=ProvinceCode.BC,
            total_amount=Decimal("112.00"),
            tax_amount=Decimal("12.00"),
            gst_amount=Decimal("5.00"),
            pst_amount=Decimal("7.00"),
        )

        itc = self.service.calculate_input_tax_credits(breakdown, gst_registered=False)

        # No ITCs if not GST registered
        assert itc.total_itc == Decimal("0.00")
        assert itc.gst_itc == Decimal("0.00")
        assert itc.pst_itc == Decimal("0.00")

    def test_calculate_input_tax_credits_ontario_hst(self):
        """Test ITC calculation for Ontario HST."""
        breakdown = TaxBreakdown(
            province=ProvinceCode.ON,
            total_amount=Decimal("113.00"),
            tax_amount=Decimal("13.00"),
            hst_amount=Decimal("13.00"),
            hst_rate=Decimal("0.13"),
        )

        itc = self.service.calculate_input_tax_credits(breakdown, gst_registered=True)

        # Full HST is ITC eligible
        assert itc.hst_itc == Decimal("13.00")
        assert itc.total_itc == Decimal("13.00")

    def test_calculate_input_tax_credits_quebec(self):
        """Test ITC calculation for Quebec GST + QST."""
        breakdown = TaxBreakdown(
            province=ProvinceCode.QC,
            total_amount=Decimal("114.98"),
            tax_amount=Decimal("14.98"),
            gst_amount=Decimal("5.00"),
            qst_amount=Decimal("9.98"),
            gst_rate=Decimal("0.05"),
            qst_rate=Decimal("0.09975"),
        )

        itc = self.service.calculate_input_tax_credits(breakdown, gst_registered=True)

        # Both GST and QST are ITC eligible in Quebec
        assert itc.gst_itc == Decimal("5.00")
        assert itc.qst_itc == Decimal("9.98")
        assert itc.total_itc == Decimal("14.98")

    def test_validate_tax_amount_valid(self):
        """Test tax amount validation with valid amounts."""
        base_amount = Decimal("100.00")

        actual_tax = Decimal("12.00")
        assert self.service.validate_tax_amount(
            base_amount, actual_tax, ProvinceCode.BC
        )

        actual_tax = Decimal("13.00")
        assert self.service.validate_tax_amount(
            base_amount, actual_tax, ProvinceCode.ON
        )

        actual_tax = Decimal("5.00")
        assert self.service.validate_tax_amount(
            base_amount, actual_tax, ProvinceCode.AB
        )

    def test_validate_tax_amount_invalid(self):
        """Test tax amount validation with invalid amounts."""
        base_amount = Decimal("100.00")

        # BC expects 12%, but got 15%
        actual_tax = Decimal("15.00")
        assert not self.service.validate_tax_amount(
            base_amount, actual_tax, ProvinceCode.BC
        )

        # Ontario expects 13%, but got 5%
        actual_tax = Decimal("5.00")
        assert not self.service.validate_tax_amount(
            base_amount, actual_tax, ProvinceCode.ON
        )

    def test_validate_tax_amount_within_tolerance(self):
        """Test tax amount validation with rounding tolerance."""
        base_amount = Decimal("100.00")

        # BC expects 12.00, got 12.02 (within default tolerance of 0.05)
        actual_tax = Decimal("12.02")
        assert self.service.validate_tax_amount(
            base_amount, actual_tax, ProvinceCode.BC
        )

        # BC expects 12.00, got 12.10 (outside default tolerance)
        actual_tax = Decimal("12.10")
        assert not self.service.validate_tax_amount(
            base_amount, actual_tax, ProvinceCode.BC
        )

    def test_get_all_provinces(self):
        """Test getting all supported provinces."""
        provinces = self.service.get_all_provinces()

        # Should include all 13 provinces/territories
        assert len(provinces) == 13
        assert ProvinceCode.BC in provinces
        assert ProvinceCode.AB in provinces
        assert ProvinceCode.ON in provinces
        assert ProvinceCode.QC in provinces
        assert ProvinceCode.YT in provinces
        assert ProvinceCode.NT in provinces
        assert ProvinceCode.NU in provinces

    def test_format_tax_summary_bc(self):
        """Test tax summary formatting for BC."""
        breakdown = TaxBreakdown(
            province=ProvinceCode.BC,
            total_amount=Decimal("112.00"),
            tax_amount=Decimal("12.00"),
            gst_amount=Decimal("5.00"),
            pst_amount=Decimal("7.00"),
            gst_rate=Decimal("0.05"),
            pst_rate=Decimal("0.07"),
        )

        itc = InputTaxCredits(total_itc=Decimal("5.00"), gst_itc=Decimal("5.00"))

        summary = self.service.format_tax_summary(breakdown, itc)

        assert "Province: BC" in summary
        assert "Tax Type: GST+PST" in summary
        assert "Total Tax: $12.00" in summary
        assert "GST (5.0%): $5.00" in summary
        assert "PST (7.0%): $7.00" in summary
        assert "Input Tax Credit: $5.00" in summary

    def test_get_provincial_config(self):
        """Test getting provincial tax configuration."""
        config = self.service.get_provincial_config(ProvinceCode.BC)

        assert config.province == ProvinceCode.BC
        assert config.gst_rate == Decimal("0.05")
        assert config.pst_rate == Decimal("0.07")
        assert config.combined_rate == Decimal("0.12")
        assert config.gst_itc_eligible is True
        assert config.pst_itc_eligible is False

    def test_get_provincial_config_invalid_province(self):
        """Test error handling for invalid province."""
        with pytest.raises(ValueError, match="Unsupported province"):
            self.service.get_provincial_config("XX")


class TestProvincialTaxIntegration:
    """Integration tests for provincial tax scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.service = ProvincialTaxService()

    def test_end_to_end_bc_restaurant_receipt(self):
        """Test complete BC restaurant receipt processing."""
        # Simulate restaurant receipt from Vancouver
        vendor_address = "123 Robson St, Vancouver, BC V6B 2W9"
        total_amount = Decimal("56.00")
        tax_amount = Decimal("6.72")  # 12% of 50.00 base

        # 1. Detect province
        detection = self.service.detect_province(vendor_address=vendor_address)
        assert detection.province == ProvinceCode.BC
        assert detection.confidence >= 0.80

        # 2. Calculate tax breakdown
        breakdown = self.service.calculate_tax_breakdown(
            total_amount, tax_amount, detection.province
        )
        assert breakdown.tax_type == "GST+PST"
        assert breakdown.gst_amount > 0
        assert breakdown.pst_amount > 0

        # 3. Calculate ITCs
        itc = self.service.calculate_input_tax_credits(breakdown, gst_registered=True)
        assert itc.gst_itc > 0
        assert itc.pst_itc == 0  # PST not ITC eligible
        assert itc.total_itc == itc.gst_itc

    def test_end_to_end_ontario_hotel_receipt(self):
        """Test complete Ontario hotel receipt processing."""
        # Simulate hotel receipt from Toronto
        vendor_address = "100 Front St W, Toronto, ON M5J 1E3"
        total_amount = Decimal("226.00")
        tax_amount = Decimal("26.00")  # 13% HST

        # 1. Detect province
        detection = self.service.detect_province(vendor_address=vendor_address)
        assert detection.province == ProvinceCode.ON

        # 2. Calculate tax breakdown
        breakdown = self.service.calculate_tax_breakdown(
            total_amount, tax_amount, detection.province
        )
        assert breakdown.tax_type == "HST"
        assert breakdown.hst_amount == tax_amount

        # 3. Calculate ITCs
        itc = self.service.calculate_input_tax_credits(breakdown, gst_registered=True)
        assert itc.hst_itc == tax_amount
        assert itc.total_itc == tax_amount

    def test_cross_canada_business_trip(self):
        """Test receipts from multiple provinces in one trip."""
        receipts = [
            # Vancouver hotel
            {
                "address": "Vancouver, BC",
                "total": Decimal("150.00"),
                "tax": Decimal("18.00"),
                "expected_province": ProvinceCode.BC,
            },
            # Calgary gas
            {
                "address": "Calgary, AB",
                "total": Decimal("75.00"),
                "tax": Decimal("3.75"),
                "expected_province": ProvinceCode.AB,
            },
            # Toronto restaurant
            {
                "address": "Toronto, ON",
                "total": Decimal("90.00"),
                "tax": Decimal("11.70"),
                "expected_province": ProvinceCode.ON,
            },
            # Montreal coffee
            {
                "address": "Montreal, QC",
                "total": Decimal("25.00"),
                "tax": Decimal("3.75"),
                "expected_province": ProvinceCode.QC,
            },
        ]

        total_itc = Decimal("0.00")

        for receipt in receipts:
            # Process each receipt
            detection = self.service.detect_province(vendor_address=receipt["address"])
            assert detection.province == receipt["expected_province"]

            breakdown = self.service.calculate_tax_breakdown(
                receipt["total"], receipt["tax"], detection.province
            )

            itc = self.service.calculate_input_tax_credits(
                breakdown, gst_registered=True
            )
            total_itc += itc.total_itc

        # Should have accumulated ITCs from all provinces
        assert total_itc > Decimal("30.00")  # Approximate expected total
