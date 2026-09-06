import csv
import io
import uuid

from app.integrations.commerce.base import CommerceOrder


class CsvImportAdapter:
    platform = "csv"

    def parse(self, content: str) -> list[CommerceOrder]:
        reader = csv.DictReader(io.StringIO(content))
        orders = []
        for row in reader:
            orders.append(
                CommerceOrder(
                    external_order_id=row.get("order_id", row.get("id", "")),
                    platform="csv",
                    customer_name=row.get("customer_name", "Unknown"),
                    customer_email=row.get("email"),
                    customer_phone=row.get("phone"),
                    currency=row.get("currency", "PKR"),
                    total_amount=float(row["total"]) if row.get("total") else None,
                    shipping_address={"raw": row.get("address", "")},
                    items=[{"name": row.get("item", "Item"), "quantity": int(row.get("quantity", 1))}],
                )
            )
        return orders
