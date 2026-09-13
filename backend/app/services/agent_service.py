from typing import Any, Dict

from app.services.customer_service import CustomerService
from app.services.policy_engine import PolicyEngine


class AgentService:
    @staticmethod
    def get_customer_summary(customer_id: str) -> Dict[str, Any]:
        customer = CustomerService.get_customer(customer_id)
        if not customer:
            raise ValueError('Customer not found')
        booking = customer.get('bookings', [{}])[0]
        return {
            'customer_id': customer['customer_id'],
            'name': customer['name'],
            'loyalty_tier': customer['loyalty_tier'],
            'email': customer['email'],
            'phone': customer['phone'],
            'pnr': booking.get('pnr'),
            'flight_number': booking.get('flight_number'),
            'route': booking.get('route'),
            'status': booking.get('status'),
            'scheduled_departure': booking.get('scheduled_departure'),
            'delay_hours': booking.get('delay_hours'),
            'reason': booking.get('reason'),
            'booking': booking,
        }

    @staticmethod
    def handle_chat(customer_id: str, message: str, fare_difference: int | None = None) -> Dict[str, Any]:
        customer = CustomerService.get_customer(customer_id)
        if not customer:
            raise ValueError('Customer not found')

        booking = customer.get('bookings', [{}])[0]
        customer_payload = {
            'customer_id': customer['customer_id'],
            'name': customer['name'],
            'loyalty_tier': customer['loyalty_tier'],
            'email': customer['email'],
            'phone': customer['phone'],
            'booking': {'pnr': booking.get('pnr'), 'flights': [booking]},
        }
        return PolicyEngine.evaluate_customer_request(customer_id, message, customer_payload, fare_difference=fare_difference)
