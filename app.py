import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
import stripe
from twilio.rest import Client
import requests

from config import Config
from models import db, User, MessageLog, Payment

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)
client = Client(app.config['TWILIO_ACCOUNT_SID'], app.config['TWILIO_AUTH_TOKEN'])
stripe.api_key = app.config['STRIPE_SECRET_KEY']


@app.before_first_request
def create_tables():
    db.create_all()


@app.route('/')
def index():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        return render_template('dashboard.html', user=user)
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        phone = request.form['phone']
        user = User.query.filter_by(phone_number=phone).first()
        if not user:
            user = User(phone_number=phone)
            db.session.add(user)
            db.session.commit()
        verification = client.verify.v2.services(app.config['TWILIO_VERIFY_SID']).verifications.create(to=phone, channel='sms')
        session['phone'] = phone
        flash('Verification code sent.')
        return redirect(url_for('verify'))
    return render_template('login.html')


@app.route('/verify', methods=['GET', 'POST'])
def verify():
    phone = session.get('phone')
    if not phone:
        return redirect(url_for('login'))
    if request.method == 'POST':
        code = request.form['code']
        result = client.verify.v2.services(app.config['TWILIO_VERIFY_SID']).verification_checks.create(to=phone, code=code)
        if result.status == 'approved':
            user = User.query.filter_by(phone_number=phone).first()
            user.verified = True
            db.session.commit()
            session['user_id'] = user.id
            flash('Logged in.')
            return redirect(url_for('index'))
        flash('Verification failed.')
    return render_template('verify.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/purchase', methods=['GET', 'POST'])
def purchase():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    user = User.query.get(session['user_id'])
    if request.method == 'POST':
        amount = float(request.form['amount'])
        if amount <= 0 or amount > 20:
            flash('Amount must be between $1 and $20.')
            return redirect(url_for('purchase'))
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {'name': 'SMS Credit'},
                    'unit_amount': int(amount * 100)
                },
                'quantity': 1
            }],
            mode='payment',
            metadata={'user_id': user.id, 'amount': amount},
            success_url=url_for('payment_success', _external=True) + '?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=url_for('purchase', _external=True)
        )
        payment = Payment(user_id=user.id, session_id=checkout_session.id, amount=amount)
        db.session.add(payment)
        db.session.commit()
        return redirect(checkout_session.url, code=303)
    return render_template('purchase.html', user=user)


@app.route('/payment/success')
def payment_success():
    session_id = request.args.get('session_id')
    if not session_id:
        return redirect(url_for('index'))
    checkout_session = stripe.checkout.Session.retrieve(session_id)
    payment = Payment.query.filter_by(session_id=session_id).first()
    if not payment:
        flash('Payment not found.')
        return redirect(url_for('index'))
    if checkout_session.payment_status == 'paid' and payment.status != 'paid':
        user = User.query.get(payment.user_id)
        user.credit += payment.amount
        payment.status = 'paid'
        db.session.commit()
        flash(f'Added ${payment.amount:.2f} credit.')
    return redirect(url_for('index'))


def deduct_credit(user, cost, direction, body):
    user.credit -= cost
    if user.credit < 0:
        user.credit = 0
    log = MessageLog(user_id=user.id, direction=direction, body=body, cost=cost)
    db.session.add(log)
    db.session.commit()


def call_openrouter(prompt):
    headers = {
        'Authorization': f'Bearer {app.config["OPENROUTER_API_KEY"]}',
        'Content-Type': 'application/json'
    }
    data = {
        'model': 'google/gemini-flash-1.5',
        'messages': [
            {'role': 'user', 'content': prompt}
        ]
    }
    resp = requests.post('https://openrouter.ai/api/v1/chat/completions', json=data, headers=headers)
    if resp.status_code == 200:
        result = resp.json()
        return result['choices'][0]['message']['content']
    return 'Error contacting model.'


@app.route('/sms', methods=['POST'])
def sms_reply():
    from_number = request.values.get('From')
    body = request.values.get('Body', '')
    user = User.query.filter_by(phone_number=from_number).first()
    if not user or user.credit <= 0:
        return ('', 204)

    cost = app.config['MESSAGE_COST']
    deduct_credit(user, cost, 'in', body)
    response_text = call_openrouter(body)
    deduct_credit(user, cost, 'out', response_text)
    client.messages.create(
        body=response_text,
        from_=app.config['TWILIO_PHONE_NUMBER'],
        to=from_number
    )
    return ('', 204)


if __name__ == '__main__':
    app.run(debug=True)
