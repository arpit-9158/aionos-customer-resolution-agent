import json
from pathlib import Path
from typing import Any, Dict, List

from app.core.config import CUSTOMERS_FILE


class CustomerService:
    @staticmethod
    def load_customers() -> List[Dict[str, Any]]:
        with open(CUSTOMERS_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

    @staticmethod
    def get_customer(customer_id: str) -> Dict[str, Any] | None:
        for customer in CustomerService.load_customers():
            if customer['customer_id'] == customer_id:
                return customer
        return None

    @staticmethod
    def get_booking_by_pnr(pnr: str) -> Dict[str, Any] | None:
        for customer in CustomerService.load_customers():
            for booking in customer.get('bookings', []):
                if booking.get('pnr') == pnr:
                    return {'customer_id': customer['customer_id'], 'customer_name': customer['name'], 'booking': booking}
        return None
