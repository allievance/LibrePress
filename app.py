from flask import Flask, render_template, request, abort, redirect, url_for, session
from models import db, Book

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///librepress.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'librepress-secret-key'
db.init_app(app)

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

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)