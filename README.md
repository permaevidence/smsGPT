# smsGPT

A simple Flask app that authenticates users via phone using Twilio Verify. Users can purchase up to $20 of credit and interact with OpenRouter's Gemini model via SMS. Each message sent or received deducts a small amount of credit.

## Setup

1. Install requirements:

```bash
pip install -r requirements.txt
```

2. Copy `.env.example` to `.env` and fill in your credentials.

3. Run the app:

```bash
flask run
```

4. Configure your Twilio phone number's webhook to point to `/sms` on your server.
