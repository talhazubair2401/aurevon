"""The sandbox provider's hosted payment page (sandbox only). It plays the external provider: the shopper picks
an outcome, the provider sends a signed callback to AureVon's webhook, and the browser returns to the shop.
"Pay without callback" leaves the callback out, to prove status checks alone confirm the payment."""

import html

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.payments import services as payments
from integrations.payments import SandboxAdapter

from ..models import SandboxPayment

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width">
<title>Sandbox payment</title></head>
<body style="font-family:system-ui;max-width:420px;margin:48px auto;padding:0 16px">
<p style="color:#8a6b4a;letter-spacing:.2em;font-size:12px">SANDBOX PAYMENT PROVIDER · TEST ONLY</p>
<h1 style="font-weight:500">Pay {currency} {amount}</h1><p>Reference {ref}</p>
<form method="post"><button name="outcome" value="succeeded" style="padding:12px 20px">Pay</button>
<button name="outcome" value="silent" style="padding:12px 20px">Pay without callback</button>
<button name="outcome" value="failed" style="padding:12px 20px">Decline</button></form></body></html>"""


@csrf_exempt  # the "provider's" own page; it has no AureVon session and changes nothing in AureVon directly
@require_http_methods(["GET", "POST"])
def sandbox_pay(request: HttpRequest, ref: str) -> HttpResponse:
    if not settings.PAYMENTS_SANDBOX_ENABLED:
        raise Http404
    sp = SandboxPayment.objects.filter(ref=ref).first()
    if sp is None:
        raise Http404
    if request.method == "GET":
        page = PAGE.format(currency=sp.currency, amount=f"{sp.amount:,.2f}", ref=html.escape(ref))
        return HttpResponse(page)
    outcome = request.POST.get("outcome", "")
    if sp.state == "pending" and outcome in ("succeeded", "silent", "failed"):
        sp.state = "failed" if outcome == "failed" else "succeeded"
        sp.save(update_fields=["state"])
        if outcome != "silent":
            kind = "payment.failed" if outcome == "failed" else "payment.succeeded"
            body, headers = SandboxAdapter.signed_event(ref, kind)
            payments.receive_webhook("sandbox", body, headers)
    return HttpResponseRedirect(sp.return_url)
