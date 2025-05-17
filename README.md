# smsGPT

A simple Flask app that authenticates users via phone using Twilio Verify. Users can purchase up to $20 of credit and interact with OpenRouter's Gemini model via SMS. Each message sent or received deducts a small amount of credit.
Payments for credit are handled through Stripe Checkout.

## Setup

1. Install requirements:

```bash
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and fill in your credentials. Make sure `SECRET_KEY` is a secure random value (e.g. `openssl rand -hex 32`).

   You'll also need a Stripe secret key in `STRIPE_SECRET_KEY` to enable credit purchases.

3. Run the app:

```bash
flask run
```

4. Configure your Twilio phone number's webhook to point to `/sms` on your server.
5. For extra security, verify incoming Twilio requests. See the [Twilio webhook security guide](https://www.twilio.com/docs/usage/webhooks/webhooks-security).
