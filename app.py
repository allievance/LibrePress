from dotenv import load_dotenv
import os
load_dotenv()
from flask import Flask, render_template, request, abort, redirect, url_for, session
import stripe
from models import db, Book
from lulu import create_print_job

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///librepress.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
db.init_app(app)
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')

@app.route('/')
def storefront():
    books = Book.query.all()
    return render_template('storefront.html', books=books)

@app.route('/book')
def book():
    pk = request.args.get('pk')
    if not pk:
        return abort(400)
    book = Book.query.get_or_404(int(pk))
    return render_template('book.html', book=book)

@app.route('/faq')
def about():
    return render_template('about.html')

@app.route('/add_to_cart')
def add_to_cart():
    pk = request.args.get('pk')
    if not pk:
        return abort (400)
    pk = int(pk)
    cart = session.get('cart', [])
    if pk not in cart:
        cart.append(pk)
    session['cart'] = cart
    return redirect(url_for('cart'))

@app.route('/cart')
def cart():
    cart_ids = session.get('cart', [])
    books = Book.query.filter(Book.id.in_(cart_ids)).all()
    total = sum(book.price for book in books)
    return render_template('cart.html', books=books, total=total)

@app.route('/remove_from_cart')
def remove_from_cart():
    pk = request.args.get('pk')
    if not pk:
        return abort(400)
    pk = int(pk)
    cart = session.get('cart', [])
    if pk in cart:
        cart.remove(pk)
    session['cart'] = cart
    return redirect(url_for('cart'))

@app.route('/shipping')
def shipping():
    cart_ids =  session.get('cart', [])
    if not cart_ids:
        return redirect(url_for('cart'))
    return render_template('shipping.html')

@app.route('/checkout', methods=['POST'])
def checkout():
    cart_ids = session.get('cart', [])
    if not cart_ids:
        return redirect(url_for('cart'))
    
    session['shipping'] = {
        'name': request.form.get('name'),
        'email': request.form.get('email'),
        'street1': request.form.get('street1'),
        'street2': request.form.get('street2'),
        'city': request.form.get('city'),
        'state': request.form.get('state'),
        'zip_code': request.form.get('zip_code'),
        'country': request.form.get('country'),
    }
    
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
        success_url='https://librepress-production.up.railway.app/success',
        cancel_url='https://librepress-production.up.railway.app/cart'
    )

    return redirect(checkout_session.url)

@app.route('/success')
def success():
    shipping = session.get('shipping', {})
    cart_ids = session.get('cart', [])
    books = Book.query.filter(Book.id.in_(cart_ids)).all()

    for book in books:
        order_data = {
            "contact_email": shipping.get('email'),
            "external_id": f"librepress-{book.id}",
            "line_items": [
                {
                    "printable_normalization": {
                        "cover": {"source_url": f"https://yourdomain.com/static/img/{book.cover_image}"},
                        "interior": {"source_url": f"https://yourdomain.com/static/img/{book.title}.pdf"},
                        "pod_package_id": "0600X0900BWSTDPB060UW444MXX"
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
                "state": shipping.get('state'),
                "postcode": shipping.get('zip_code'),
                "country_code": shipping.get('country'),
            },
            "shipping_level": "MAIL"
        }
        create_print_job(order_data)
    
    session.pop('cart', None)
    session.pop('shipping', None)
    return render_template('success.html')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)# redeploy
