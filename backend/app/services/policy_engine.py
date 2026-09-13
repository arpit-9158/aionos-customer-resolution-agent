import re
from typing import Any, Dict, List


class PolicyEngine:
    CANCELLATION_WINDOW_HOURS = 24
    FARE_DIFF_THRESHOLD = 1500
    MEAL_VOUCHER_AMOUNT = 500

    @staticmethod
    def _normalize_message(message: str) -> str:
        return (message or '').lower().strip()

    @staticmethod
    def _customer_status(customer_data: Dict[str, Any]) -> Dict[str, Any]:
        booking = customer_data.get('booking', {})
        flights = booking.get('flights', []) if isinstance(booking, dict) else []
        if not flights:
            flights = customer_data.get('bookings', [])
        if not flights:
            return {'booking': booking, 'flight': None}
        return {'booking': booking, 'flight': flights[0]}

    @classmethod
    def evaluate_customer_request(
        cls,
        customer_id: str,
        message: str,
        customer_data: Dict[str, Any],
        fare_difference: int | None = None,
    ) -> Dict[str, Any]:
        normalized = cls._normalize_message(message)
        flight = cls._customer_status(customer_data)['flight'] or {}
        delay_hours = float(flight.get('delay_hours', 0) or 0)

        allowed_actions: List[Dict[str, Any]] = []
        recommended_actions: List[Dict[str, Any]] = []
        escalation = {'required': False, 'reason': None}
        policy_references: List[str] = []

        if 'legal' in normalized or 'formal complaint' in normalized or 'complaint' in normalized or 'threaten' in normalized:
            escalation = {
                'required': True,
                'reason': 'Customer threatens legal action or formal complaint; escalate to a human agent.'
            }
            recommended_actions.append({'type': 'escalate', 'label': 'Escalate to Human', 'reason': escalation['reason']})
            return {
                'message': 'I understand this is serious. A formal complaint or legal threat requires human escalation under the current policy.',
                'intent': 'complaint_or_legal_threat',
                'resolution': 'Escalation required',
                'allowed_actions': [],
                'recommended_actions': recommended_actions,
                'escalation': escalation,
                'policy_references': ['Legal/formal complaint -> escalate'],
                'booking_context': customer_data,
            }

        if flight.get('status') == 'cancelled' or 'cancelled' in normalized:
            policy_references.append('If airline cancels a flight: free rebooking within 24 hours or full refund.')
            if customer_data.get('loyalty_tier') in ('Gold', 'Platinum'):
                policy_references.append('Gold and Platinum get priority rebooking.')

            allowed_actions.append({
                'type': 'rebook',
                'label': 'Rebook on next available flight',
                'status': 'allowed',
                'reason': 'Airline-caused cancellation qualifies for free rebooking within 24 hours.',
                'details': {'window_hours': 24, 'cost': 0, 'priority': 'priority rebooking'},
            })
            allowed_actions.append({
                'type': 'refund',
                'label': 'Initiate full refund',
                'status': 'allowed',
                'reason': 'Airline-caused cancellation qualifies for a full refund to the original payment method.',
                'details': {'amount': 'Full refund', 'timing': 'Within 7 business days', 'payment_method': 'Original payment method'},
            })
            recommended_actions.append({'type': 'refund', 'label': 'Process refund', 'reason': 'Full refund is the standard option for an airline-caused cancellation.'})

        if flight.get('status') == 'delayed' or 'delay' in normalized:
            if delay_hours < 3:
                allowed_actions.append({
                    'type': 'meal_voucher',
                    'label': '₹500 meal voucher',
                    'status': 'allowed',
                    'reason': 'Delay under 3 hours qualifies for a ₹500 meal voucher.',
                    'details': {'amount': 500, 'coverage': 'meal voucher'}
                })
                recommended_actions.append({'type': 'meal_voucher', 'label': 'Meal voucher', 'reason': 'A short delay qualifies for ₹500 meal voucher.'})
            elif delay_hours > 3:
                allowed_actions.append({
                    'type': 'meal_voucher',
                    'label': '₹500 meal voucher',
                    'status': 'allowed',
                    'reason': 'Delay more than 3 hours qualifies for a meal voucher.',
                    'details': {'amount': 500, 'coverage': 'meal voucher'}
                })
                allowed_actions.append({
                    'type': 'lounge_access',
                    'label': 'Lounge access',
                    'status': 'allowed',
                    'reason': 'Delay more than 3 hours qualifies for lounge access.',
                    'details': {'coverage': 'lounge access'}
                })
                recommended_actions.append({'type': 'meal_voucher', 'label': 'Meal voucher', 'reason': 'Delay exceeds the 3-hour threshold.'})
                recommended_actions.append({'type': 'lounge_access', 'label': 'Lounge access', 'reason': 'Lounge access is available for delays over 3 hours.'})

            if delay_hours > 5:
                allowed_actions.append({
                    'type': 'hotel',
                    'label': 'Hotel accommodation',
                    'status': 'allowed',
                    'reason': 'Delay more than 5 hours qualifies for hotel accommodation for the delayed hours only.',
                    'details': {'coverage': 'delayed hours only'}
                })
                recommended_actions.append({'type': 'hotel', 'label': 'Hotel accommodation', 'reason': 'Hotel support applies only for the delayed hours, not a full night.'})

        if 'upgrade' in normalized or 'business class' in normalized:
            escalation = {
                'required': True,
                'reason': 'Business-class upgrade is not covered by the supplied policy and requires a human exception review.'
            }
            recommended_actions.append({'type': 'upgrade', 'label': 'Escalate unsupported upgrade request', 'reason': 'No policy support for a complimentary business-class upgrade.'})

        fare_diff = fare_difference if fare_difference is not None else cls._extract_fare_difference(normalized)
        if fare_diff > 0:
            if fare_diff > cls.FARE_DIFF_THRESHOLD:
                escalation = {
                    'required': True,
                    'reason': f'Fare difference of ₹{fare_diff} exceeds the ₹{cls.FARE_DIFF_THRESHOLD} waiver threshold and requires supervisor approval.'
                }
                recommended_actions.append({'type': 'fare_difference', 'label': 'Escalate fare-waiver request', 'reason': escalation['reason']})
            else:
                policy_references.append('If customer voluntarily chooses a higher-fare flight: customer pays the fare difference; agents cannot waive fare differences above ₹1,500 without supervisor approval.')
                if 'rebook' in normalized or 'flight' in normalized or 'higher fare' in normalized:
                    allowed_actions.append({
                        'type': 'rebook',
                        'label': 'Rebook on higher-fare flight',
                        'status': 'allowed',
                        'reason': 'Rebooking is allowed, but the customer pays the fare difference unless it is waived by supervisor approval.',
                        'details': {'fare_difference': fare_diff, 'waiver_status': 'not auto-waived'}
                    })

        if 'hotel' in normalized and delay_hours <= 5:
            recommended_actions.append({'type': 'hotel', 'label': 'Not eligible for hotel', 'reason': 'Hotel applies only when the delay exceeds 5 hours.'})

        if 'complaint' in normalized or 'legal' in normalized:
            escalation = {'required': True, 'reason': 'Customer threatens legal action or formal complaint; escalate to a human agent.'}
            recommended_actions.append({'type': 'escalate', 'label': 'Escalate to Human', 'reason': escalation['reason']})

        if 'waive' in normalized and fare_diff > cls.FARE_DIFF_THRESHOLD:
            escalation = {'required': True, 'reason': f'Fare difference waiver request of ₹{fare_diff} exceeds the ₹{cls.FARE_DIFF_THRESHOLD} approval threshold.'}
            recommended_actions.append({'type': 'fare_difference', 'label': 'Escalate fare-waiver request', 'reason': escalation['reason']})

        if not allowed_actions and not recommended_actions and not escalation['required']:
            return {
                'message': 'I do not have enough information in the provided airline data to confirm that.',
                'intent': 'unknown',
                'resolution': 'Need more information',
                'allowed_actions': [],
                'recommended_actions': [],
                'escalation': {'required': False, 'reason': None},
                'policy_references': ['Insufficient data in the provided airline policy.'],
                'booking_context': customer_data,
            }

        if 'hotel' in normalized and delay_hours > 5:
            allowed_actions = sorted(allowed_actions, key=lambda action: 0 if action.get('type') == 'hotel' else 1)

        unique_allowed = []
        seen_allowed = set()
        for action in allowed_actions:
            key = action.get('type')
            if key not in seen_allowed:
                unique_allowed.append(action)
                seen_allowed.add(key)

        unique_recommended = []
        seen_recommended = set()
        for action in recommended_actions:
            key = action.get('type')
            if key not in seen_recommended:
                unique_recommended.append(action)
                seen_recommended.add(key)

        return {
            'message': cls._build_response_message(flight, normalized, escalation, customer_data, unique_allowed),
            'intent': cls._detect_intent(normalized, flight),
            'resolution': 'Resolution determined by policy' if unique_allowed or escalation['required'] else 'No policy-backed action found',
            'allowed_actions': unique_allowed,
            'recommended_actions': unique_recommended,
            'escalation': escalation,
            'policy_references': list(dict.fromkeys(policy_references)),
            'booking_context': customer_data,
        }

    @staticmethod
    def _detect_intent(normalized: str, flight: Dict[str, Any]) -> str:
        if 'refund' in normalized or 'money back' in normalized:
            return 'refund'
        if 'rebook' in normalized or 'another flight' in normalized:
            return 'rebooking'
        if 'upgrade' in normalized or 'business class' in normalized:
            return 'upgrade'
        if 'hotel' in normalized:
            return 'hotel'
        if 'lounge' in normalized:
            return 'lounge_access'
        if 'voucher' in normalized or 'meal' in normalized:
            return 'meal_voucher'
        if 'delay' in normalized:
            return 'delay'
        if flight.get('status') == 'cancelled' or 'cancelled' in normalized:
            return 'cancellation'
        if 'complaint' in normalized or 'legal' in normalized:
            return 'complaint_or_legal_threat'
        return 'general_enquiry'

    @staticmethod
    def _extract_fare_difference(normalized: str) -> int:
        amount_match = re.search(r'(?:₹|\brs\.?\b|\binr\b)\s*([\d,]+)', normalized, re.IGNORECASE)
        if not amount_match and ('fare difference' in normalized or 'higher fare' in normalized):
            amount_match = re.search(r'(?:fare difference|higher fare)[^\d]{0,24}([\d,]+)', normalized, re.IGNORECASE)
        if not amount_match:
            return 0
        return int(amount_match.group(1).replace(',', ''))

    @staticmethod
    def _build_response_message(flight, normalized, escalation, customer_data, allowed_actions):
        if flight.get('status') == 'cancelled':
            if escalation['required']:
                return 'I understand this is frustrating. The cancellation qualifies for either a free rebooking within 24 hours or a full refund, but the additional request is outside the policy and requires escalation.'
            return 'I understand this is frustrating. Your flight was cancelled due to operational reasons. Under the available policy, you can either be rebooked on the next available flight within 24 hours at no charge or request a full refund. The refund is processed within 7 business days to the original payment method.'

        if flight.get('status') == 'delayed':
            delay_hours = float(flight.get('delay_hours', 0) or 0)
            if delay_hours > 5:
                if escalation['required']:
                    return 'I understand this delay is disruptive. The policy includes a meal voucher, lounge access, and hotel accommodation for delayed hours only. The requested exception also requires supervisor approval before it can be considered.'
                return 'I understand this delay is disruptive. Your flight is delayed by more than 5 hours, so the policy includes a meal voucher, lounge access, and hotel accommodation covering only the delayed hours. It does not include a full-night hotel stay.'
            if delay_hours > 3:
                return 'I understand this delay is frustrating. Your flight is delayed by 4 hours, so the policy provides a ₹500 meal voucher and lounge access. Hotel accommodation is not available because it applies only to delays above 5 hours.'
            return 'I understand this delay is frustrating. Your flight is delayed less than 3 hours, so the policy provides a ₹500 meal voucher only.'

        if 'upgrade' in normalized or 'business class' in normalized:
            return "I can help with the options covered by the available policy. A complimentary business-class upgrade on an unaffected return flight isn't provided for under the supplied policy, so I can't approve that request directly."

        if escalation['required']:
            return escalation['reason']
        return 'I do not have enough information in the provided airline data to confirm that.'
