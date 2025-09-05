from pydantic import BaseModel


class ReceiptData(BaseModel):
    vendor_name: str
    amount: float
    date: str
    currency: str = "USD"
    category: str
    tax_amount: float = 0.0


class LineItem(BaseModel):
    description: str
    amount: float
    quantity: int = 1

