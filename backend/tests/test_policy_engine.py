from app.services.policy_engine import PolicyEngine


def test_priya_refund_allowed():
    result = PolicyEngine.evaluate_customer_request(
        customer_id='priya-nair',
        message='I want a full refund for my cancelled flight.',
        customer_data={
            'customer_id': 'priya-nair',
            'loyalty_tier': 'Gold',
            'booking': {
                'pnr': 'SK4821X',
                'flights': [
                    {'flight_number': 'SK-204', 'status': 'cancelled', 'airline_caused': True, 'route': 'Delhi → Goa'}
                ],
            },
        },
    )
    assert result['allowed_actions']
    assert any(action['type'] == 'refund' for action in result['allowed_actions'])
    assert not result['escalation']['required']


def test_priya_rebooking_allowed():
    result = PolicyEngine.evaluate_customer_request(
        customer_id='priya-nair',
        message='Can you rebook me on the next available flight within 24 hours?',
        customer_data={
            'customer_id': 'priya-nair',
            'loyalty_tier': 'Gold',
            'booking': {
                'pnr': 'SK4821X',
                'flights': [
                    {'flight_number': 'SK-204', 'status': 'cancelled', 'airline_caused': True, 'route': 'Delhi → Goa'}
                ],
            },
        },
    )
    assert any(action['type'] == 'rebook' for action in result['allowed_actions'])


def test_priya_business_upgrade_not_authorized():
    result = PolicyEngine.evaluate_customer_request(
        customer_id='priya-nair',
        message='I want a free business class upgrade on my return flight.',
        customer_data={
            'customer_id': 'priya-nair',
            'loyalty_tier': 'Gold',
            'booking': {
                'pnr': 'SK4821X',
                'flights': [
                    {'flight_number': 'SK-204', 'status': 'cancelled', 'airline_caused': True, 'route': 'Delhi → Goa'},
                    {'flight_number': 'SK-205', 'status': 'active', 'route': 'Goa → Delhi'}
                ],
            },
        },
    )
    assert result['escalation']['required'] is True
    assert any(action['type'] == 'upgrade' for action in result['recommended_actions'])


def test_arvind_four_hour_delay_meal_and_lounge_allowed():
    result = PolicyEngine.evaluate_customer_request(
        customer_id='arvind-kulkarni',
        message='My flight is delayed by four hours, can I get a meal voucher and lounge access?',
        customer_data={
            'customer_id': 'arvind-kulkarni',
            'loyalty_tier': 'Silver',
            'booking': {'pnr': 'TR1190B', 'flights': [{'flight_number': 'SK-118', 'status': 'delayed', 'delay_hours': 4.0}]},
        },
    )
    action_types = {action['type'] for action in result['allowed_actions']}
    assert 'meal_voucher' in action_types
    assert 'lounge_access' in action_types


def test_arvind_hotel_not_allowed_for_4_hour_delay():
    result = PolicyEngine.evaluate_customer_request(
        customer_id='arvind-kulkarni',
        message='I need a hotel because of this delay.',
        customer_data={
            'customer_id': 'arvind-kulkarni',
            'loyalty_tier': 'Silver',
            'booking': {'pnr': 'TR1190B', 'flights': [{'flight_number': 'SK-118', 'status': 'delayed', 'delay_hours': 4.0}]},
        },
    )
    assert all(action['type'] != 'hotel' for action in result['allowed_actions'])
    assert any(action['type'] == 'hotel' for action in result['recommended_actions'])


def test_meher_delay_meal_and_lounge_allowed():
    result = PolicyEngine.evaluate_customer_request(
        customer_id='meher-kaur',
        message='My flight is delayed six hours; I need the travel support covered by the policy.',
        customer_data={
            'customer_id': 'meher-kaur',
            'loyalty_tier': 'Platinum',
            'booking': {'pnr': 'WL7742', 'flights': [{'flight_number': 'SK-305', 'status': 'delayed', 'delay_hours': 6.0}]},
        },
    )
    action_types = {action['type'] for action in result['allowed_actions']}
    assert 'meal_voucher' in action_types
    assert 'lounge_access' in action_types


def test_meher_hotel_delayed_hours_only():
    result = PolicyEngine.evaluate_customer_request(
        customer_id='meher-kaur',
        message='I want a full night hotel stay.',
        customer_data={
            'customer_id': 'meher-kaur',
            'loyalty_tier': 'Platinum',
            'booking': {'pnr': 'WL7742', 'flights': [{'flight_number': 'SK-305', 'status': 'delayed', 'delay_hours': 6.0}]},
        },
    )
    assert any(action['type'] == 'hotel' for action in result['allowed_actions'])
    assert result['allowed_actions'][0]['details']['coverage'] == 'delayed hours only'


def test_meher_fare_difference_requires_supervisor_escalation():
    result = PolicyEngine.evaluate_customer_request(
        customer_id='meher-kaur',
        message='I want to switch to another flight and waive the ₹2,000 fare difference.',
        customer_data={
            'customer_id': 'meher-kaur',
            'loyalty_tier': 'Platinum',
            'booking': {'pnr': 'WL7742', 'flights': [{'flight_number': 'SK-305', 'status': 'delayed', 'delay_hours': 6.0}]},
        },
        fare_difference=2000,
    )
    assert result['escalation']['required'] is True
    assert 'fare difference' in result['escalation']['reason'].lower()


def test_fare_difference_in_customer_message_is_extracted_and_never_waived():
    result = PolicyEngine.evaluate_customer_request(
        customer_id='meher-kaur',
        message='The fare difference is ₹2,000. Waive it.',
        customer_data={
            'customer_id': 'meher-kaur',
            'loyalty_tier': 'Platinum',
            'booking': {'pnr': 'WL7742', 'flights': [{'flight_number': 'SK-305', 'status': 'delayed', 'delay_hours': 6.0}]},
        },
    )
    assert result['escalation']['required'] is True
    assert not any(action.get('status') == 'allowed' and action['type'] == 'fare_difference' for action in result['allowed_actions'])


def test_fare_difference_under_threshold_is_not_auto_waived():
    result = PolicyEngine.evaluate_customer_request(
        customer_id='meher-kaur',
        message='I want a higher fare flight and need the fare difference waived.',
        customer_data={
            'customer_id': 'meher-kaur',
            'loyalty_tier': 'Platinum',
            'booking': {'pnr': 'WL7742', 'flights': [{'flight_number': 'SK-305', 'status': 'delayed', 'delay_hours': 6.0}]},
        },
        fare_difference=1500,
    )
    assert result['escalation']['required'] is False
    assert any(action['type'] == 'rebook' for action in result['allowed_actions'])


def test_legal_complaint_requires_escalation():
    result = PolicyEngine.evaluate_customer_request(
        customer_id='priya-nair',
        message='I am filing a formal complaint and threatening legal action.',
        customer_data={
            'customer_id': 'priya-nair',
            'loyalty_tier': 'Gold',
            'booking': {'pnr': 'SK4821X', 'flights': [{'flight_number': 'SK-204', 'status': 'cancelled', 'airline_caused': True}]},
        },
    )
    assert result['escalation']['required'] is True
    assert 'legal' in result['escalation']['reason'].lower() or 'complaint' in result['escalation']['reason'].lower()
