from contextlib import asynccontextmanager
from typing import Any, Dict, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.core.config import DEBUG, FRONTEND_ORIGIN
from app.services.agent_service import AgentService
from app.services.customer_service import CustomerService


class ChatRequest(BaseModel):
    customer_id: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    fare_difference: int | None = None


class ActionRequest(BaseModel):
    customer_id: str = Field(..., min_length=1)
    action_type: str = Field(..., min_length=1)
    request: str = Field(..., min_length=1)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title='AIONOS Resolution Agent', version='1.0.0', lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_ORIGIN] if FRONTEND_ORIGIN else ['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


@app.get('/api/health')
def health() -> Dict[str, Any]:
    return {'status': 'ok', 'debug': DEBUG}


@app.get('/api/customers')
def get_customers() -> List[Dict[str, Any]]:
    return CustomerService.load_customers()


@app.get('/api/customers/{customer_id}')
def get_customer(customer_id: str) -> Dict[str, Any]:
    customer = CustomerService.get_customer(customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail='Customer not found')
    return customer


@app.get('/api/bookings/{pnr}')
def get_booking_by_pnr(pnr: str) -> Dict[str, Any]:
    booking = CustomerService.get_booking_by_pnr(pnr)
    if not booking:
        raise HTTPException(status_code=404, detail='Booking not found')
    return booking


@app.get('/api/policies')
def get_policies() -> Dict[str, Any]:
    return {
        'cancellation': {
            'type': 'airline_cancellation',
            'options': ['free rebooking within 24 hours', 'full refund'],
            'refund_processing': 'within 7 business days',
            'payment_method': 'original payment method only',
        },
        'delay': {
            'less_than_3_hours': {'meal_voucher': 500},
            'more_than_3_hours': {'meal_voucher': 500, 'lounge_access': True},
            'more_than_5_hours': {'meal_voucher': 500, 'lounge_access': True, 'hotel': 'delayed hours only'},
        },
        'loyalty': {
            'gold_platinum': 'priority rebooking',
            'extra_compensation': 'not beyond standard policy',
        },
        'fare_difference': {
            'threshold': 1500,
            'approval_required_when_above': True,
            'customer_pays_difference_if_voluntary_higher_fare': True,
        },
    }


@app.post('/api/chat')
def chat(request: ChatRequest) -> Dict[str, Any]:
    try:
        result = AgentService.handle_chat(request.customer_id, request.message, request.fare_difference)
        return result
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post('/api/actions')
def create_action(request: ActionRequest) -> Dict[str, Any]:
    if not CustomerService.get_customer(request.customer_id):
        raise HTTPException(status_code=404, detail='Customer not found')
    supported_actions = {'refund', 'rebook', 'meal_voucher', 'lounge_access', 'hotel', 'upgrade', 'fare_difference', 'escalate'}
    if request.action_type not in supported_actions:
        raise HTTPException(status_code=400, detail='Unsupported action type')
    return {
        'status': 'created',
        'action_type': request.action_type,
        'message': 'Request recorded and queued for the appropriate airline or human review. No external action was completed.',
    }


@app.get('/api/resolutions/{resolution_id}')
def resolution_stub(resolution_id: str) -> Dict[str, Any]:
    return {'resolution_id': resolution_id, 'status': 'stored'}
