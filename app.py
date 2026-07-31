# -------------------------------------------------------------------------------------
# IMPORTS
# -------------------------------------------------------------------------------------
from dotenv import load_dotenv
import os
import ast
import json

load_dotenv()

from flask import Flask, render_template, request, abort, redirect, url_for, session
from flask_mail import Mail, Message
import stripe
from models import db, Book
from lulu import create_print_job
from config import Config

# -------------------------------------------------------------------------------------
# CONFIRMATION EMAIL
# -------------------------------------------------------------------------------------
mail = Mail()

def send_confirmation_email(customer_email, customer_name, books, shipping):
    subject = "Your LibrePress Order Confirmation"

    book_list = "\n".join([f"- {book.title} by {book.author}: ${book.price}" for book in books])

    body = f"""Dear {customer_name},

Thank you for your order from LibrePress.

ORDER SUMMARY
{book_list}

SHIPPING TO
{shipping.get('name')}
{shipping.get('street1')}
{shipping.get('street2', '')}
{shipping.get('city')}, {shipping.get('state')} {shipping.get('zip_code')}
{shipping.get('country')}

Your book will be printed and shipped by Lulu. Estimated delivery is 15-20 business days depending on your location.

If you have any questions about your order, please contact us at info@librepress.us.

Thank you for supporting independent publishing.

LibrePress
librepress.us
"""

    msg = Message(
        subject=subject,
        recipients=[customer_email],
        body=body
    )

    mail.send(msg)

# -------------------------------------------------------------------------------------
# CREATE APP
# -------------------------------------------------------------------------------------
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    mail.init_app(app)
    stripe.api_key = app.config['STRIPE_SECRET_KEY']

    return app

app = create_app()

# -------------------------------------------------------------------------------------
# ROUTES
# -------------------------------------------------------------------------------------

# Storefront

@app.route('/')
def storefront():
    books = Book.query.all()
    return render_template('storefront.html', books=books)

# Book listing

@app.route('/book')
def book():
    pk = request.args.get('pk')
    if not pk:
        return abort(400)
    book = Book.query.get_or_404(int(pk))
    return render_template('book.html', book=book)

# About page

@app.route('/faq')
def about():
    return render_template('about.html')

# Add-to-cart

@app.route('/add_to_cart', methods=['POST'])
def add_to_cart():
    pk = request.form.get('pk')
    if not pk:
        return abort (400)
    pk = int(pk)
    cart = session.get('cart', [])
    if pk not in cart:
        cart.append(pk)
    session['cart'] = cart
    return redirect(url_for('cart'))

# Cart

@app.route('/cart')
def cart():
    cart_ids = session.get('cart', [])
    books = Book.query.filter(Book.id.in_(cart_ids)).all()
    total = sum(book.price for book in books)
    return render_template('cart.html', books=books, total=total)

# Remove-from-Cart

@app.route('/remove_from_cart', methods=['POST'])
def remove_from_cart():
    pk = request.form.get('pk')
    if not pk:
        return abort(400)
    pk = int(pk)
    cart = session.get('cart', [])
    if pk in cart:
        cart.remove(pk)
    session['cart'] = cart
    return redirect(url_for('cart'))

# Shipping

@app.route('/shipping')
def shipping():
    cart_ids =  session.get('cart', [])
    if not cart_ids:
        return redirect(url_for('cart'))
    return render_template('shipping.html')

# Checkout

@app.route('/checkout', methods=['POST'])
def checkout():
    cart_ids = session.get('cart', [])
    if not cart_ids:
        return redirect(url_for('cart'))
    
    shipping_data = {
        'name': request.form.get('name'),
        'email': request.form.get('email'),
        'street1': request.form.get('street1'),
        'street2': request.form.get('street2'),
        'city': request.form.get('city'),
        'state': request.form.get('state'),
        'zip_code': request.form.get('zip_code'),
        'country': request.form.get('country'),
        'phone': request.form.get('phone'),
    }

    session['shipping'] = shipping_data
    
    books = Book.query.filter(Book.id.in_(cart_ids)).all()

    line_items = []
    for book in books:
        line_items.append({
            'price_data': {
                'currency': 'usd',
                'product_data': {
                    'name': book.title,
                },
                'unit_amount': int(book.price * 100),
            },
            'quantity': 1,
        })

    checkout_session = stripe.checkout.Session.create(
        payment_method_types=['card'],
        line_items=line_items,
        mode='payment',
        success_url='https://librepress.us/success',
        cancel_url='https://librepress.us/cart',
        metadata={
            'cart_ids': ','.join(str(id) for id in cart_ids),
            'shipping': json.dumps(shipping_data)
        }
    )

    return redirect(checkout_session.url)

# Success

@app.route('/success')
def success():
    session.pop('cart', None)
    session.pop('shipping', None)
    return render_template('success.html')

# Stripe Webhook

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.getenv('STRIPE_WEBHOOK_SECRET')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
    except ValueError:
        return 'Invalid payload', 400
    except stripe.error.SignatureVerificationError:
        return 'Invalid signature', 400

    if event['type'] == 'checkout.session.completed':
        session_data = event['data']['object']
        customer_email = session_data['customer_details']['email']

        metadata = session_data['metadata']
    
        cart_ids = [int(id) for id in metadata['cart_ids'].split(',') if id]
        shipping = json.loads(metadata['shipping'])

        books = Book.query.filter(Book.id.in_(cart_ids)).all()

        for book in books:
            order_data = {
                "contact_email": customer_email,
                "external_id": f"librepress-{book.id}-{session_data['id']}",
                "line_items": [
                    {
                        "printable_normalization": {
                            "cover": {"source_url": f"https://librepress.us/static/pdf/{book.cover_pdf}"},
                            "interior": {"source_url": f"https://librepress.us/static/pdf/{book.interior_pdf}"},
                            "pod_package_id": app.config['POD_PACKAGE_ID']
                        },
                        "quantity": 1,
                        "title": book.title
                    }
                ],
                "shipping_address": {
                    "name": shipping.get('name'),
                    "street1": shipping.get('street1'),
                    "street2": shipping.get('street2'),
                    "city": shipping.get('city'),
                    "state_code": shipping.get('state'),
                    "postcode": shipping.get('zip_code'),
                    "country_code": shipping.get('country'),
                    "phone_number": shipping.get('phone'),
                },
                "shipping_level": "MAIL"
            }
        
            result = create_print_job(order_data)
        
            if result:
                print(f"Print job created for {book.title}")
                send_confirmation_email(
                    customer_email,
                    shipping.get('name'),
                    books,
                    shipping
                )
            else:
                print(f"Print job failed for {book.title}")
                
    return 'OK', 200

# 404 - Page Not Found

@app.errorhandler(404)
def page_not_found(e):
    return render_template('404.html'), 404

# 500 - Internal Server Error

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('500.html'), 500

# -------------------------------------------------------------------------------------
# DEBUGGER
# -------------------------------------------------------------------------------------
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
