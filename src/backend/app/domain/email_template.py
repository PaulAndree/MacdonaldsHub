"""The one email template (RN-14). Its text is an example until P-03 is decided.

The only variable is the incident number (Order ID): no amounts and no free description (P-03).
"""

TEMPLATE_VERSION = "example-1"
SUBJECT = "Reclamación de incidente"
BODY = (
    "Estimados socios Ubereats, remitimos el siguiente incidente No Incidente {orderId} "
    "para su reclamación. Un saludo Macdonalds"
)
PENDING_DECISION = "P-03"


def render_body(order_id: str) -> str:
    return BODY.replace("{orderId}", order_id)
