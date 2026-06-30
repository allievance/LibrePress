from dotenv import load_dotenv
import os
load_dotenv()
from flask import Flask, render_template, request, abort, redirect, url_for, session
import stripe
import ast
from models import db, Book
from lulu import create_print_job

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///librepress.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
db.init_app(app)
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY')

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

# Cart

@app.route('/cart')
def cart():
    cart_ids = session.get('cart', [])
    books = Book.query.filter(Book.id.in_(cart_ids)).all()
    total = sum(book.price for book in books)
    return render_template('cart.html', books=books, total=total)

# Remove-from-Cart

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
            'shipping': str(shipping_data)
        }
    )

    return redirect(checkout_session.url)

# Success

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
                        "cover": {"source_url": f"https://librepress.us/static/pdf/{book.cover_pdf}"},
                        "interior": {"source_url": f"https://librepress.us/static/pdf/{book.interior_pdf}"},
                        "pod_package_id": "0583X0827BWSTDPB060UC444MXX"
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
            },
            "shipping_level": "MAIL"
        }
        create_print_job(order_data)
    
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

        metadata = session_data.get('metadata', {})
    
        cart_ids = [int(id) for id in metadata.get('cart_ids', '').split(',') if id]
        shipping = ast.literal_eval(metadata.get('shipping', '{}'))

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
                            "pod_package_id": "0583X0827BWSTDPB060UC444MXX"
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
                },
                "shipping_level": "MAIL"
            }
        
            result = create_print_job(order_data)
        
            if result:
                print(f"Print job created for {book.title}")
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

# Reseed function - DO NOT SHARE

@app.route('/admin/reseed?key=19$k0p$+y12')
def reseed():
    Book.query.delete()
    db.session.commit()
    
    books = [
        Book(title="The Book of the Courtier", author="Baldassare Castiglione", language="English", price=51.48, description="A foundational Renaissance dialogue, <i>The Book of the Courtier</i> explores the qualities of the ideal noble through elegant conversation set in the court of Urbino. Participants debate grace, virtue, wit, and the elusive art of sprezzatura, or effortless mastery. The work reflects a world where appearance and character intertwine, shaping political and social success. This special edition contains several illustrated plates and over 300 annotations, guiding modern readers through historical context and linguistic nuance. Both a manual of conduct and a philosophical meditation, it remains a timeless study of human excellence, performance, and the subtle dynamics of power.", cover_image="TheBookOfTheCourtier.jpg", cover_pdf="TheBookOfTheCourtier_Cover.pdf", interior_pdf="TheBookOfTheCourtier_Interior.pdf", page_count=750),
        Book(title="The Ego and Its Own", author="Max Stirner", language="English", price=40.44, description="Max Stirner's <i>The Ego and Its Own</i> is a radical exploration of individualism that dismantles all external authorities, including religion, morality, and the state. Stirner argues that abstract ideals, which he calls “spooks,” dominate human life by demanding submission to illusions. In their place, he proposes the sovereign individual, guided solely by self-interest and personal will. The work is provocative, irreverent, and deeply philosophical, challenging readers to confront the foundations of belief and obligation. Both celebrated and controversial, it has influenced anarchism, existentialism, and post-structural thought, offering a fierce defense of personal autonomy against all forms of imposed identity.", cover_image="TheEgoAndItsOwn.jpg", cover_pdf="TheEgoAndItsOwn_Cover.pdf", interior_pdf="TheEgoAndItsOwn_Interior.pdf", page_count=529),
        Book(title="The Conquest of Bread", author="Peter Kropotkin", language="English", price=30.08, description="In <i>The Conquest of Bread</i>, Peter Kropotkin presents a compelling vision of anarchist communism grounded in cooperation, mutual aid, and the abolition of private property. Rejecting both state control and capitalist exploitation, he argues that modern society possesses the productive capacity to ensure abundance for all. Through clear reasoning and practical examples, Kropotkin outlines how communities might organize labor, distribution, and daily life without coercion. The work critiques inequality while offering a hopeful alternative rooted in solidarity and human dignity. Both radical and pragmatic, it remains a cornerstone of libertarian socialist thought and a powerful challenge to conventional economic systems.", cover_image="TheConquestOfBread.jpg", cover_pdf="TheConquestOfBread_Cover.pdf", interior_pdf="TheConquestOfBread_Interior.pdf", page_count=322),
        Book(title="The Crisis of the Modern World", author="René Guénon", language="English", price=23.04, description="René Guénon's <i>The Crisis of the Modern World</i> offers a penetrating critique of modernity, arguing that contemporary civilization has abandoned metaphysical truth in favor of materialism and fragmentation. Drawing on traditionalist philosophy, Guénon contrasts ancient spiritual unity with the disintegration of modern thought, where quantity replaces quality and intuition yields to rationalism alone. He warns that this imbalance leads to cultural and intellectual decline. The work calls for a return to timeless principles rooted in sacred knowledge. Dense yet provocative, it challenges readers to reconsider the foundations of progress, knowledge, and civilization itself in an increasingly disoriented world.", cover_image="TheCrisisOfTheModernWorld.jpg", cover_pdf="TheCrisisOfTheModernWorld_Cover.pdf", interior_pdf="TheCrisisOfTheModernWorld_Interior.pdf", page_count=181),
        Book(title="God and the State", author="Mikhail Bakunin", language="English", price=19.38, description="Mikhail Bakunin's <i>God and the State</i> is a passionate critique of religion and political authority, arguing that both serve to oppress human freedom. Bakunin contends that belief in divine power justifies submission to earthly rulers, reinforcing systems of domination. He champions atheism and revolutionary anarchism as paths toward liberation, where individuals can realize their full potential without coercion. Written with urgency and rhetorical force, the work blends philosophy and political theory into a call for action. It remains a foundational text in anarchist thought, challenging readers to question the legitimacy of authority and envision a society built on freedom and equality.", cover_image="GodAndTheState.jpg", cover_pdf="GodAndTheState_Cover.pdf", interior_pdf="GodAndTheState_Interior.pdf", page_count=108),
        Book(title="The King in Yellow", author="Robert W. Chambers", language="English", price=29.58, description="Robert W. Chambers' <i>The King in Yellow</i> is a haunting collection of interconnected stories that blend horror, decadence, and psychological unease. At its center lies a forbidden play that drives readers into madness, its influence spreading through artists, lovers, and dreamers alike. The tales move between reality and nightmare, evoking a world where beauty conceals dread and knowledge carries a terrible cost. Rich in atmosphere and symbolism, the work helped shape early weird fiction and cosmic horror. Both eerie and enigmatic, it invites readers into a realm where perception falters and the boundaries of sanity dissolve.", cover_image="TheKingInYellow.jpg", cover_pdf="TheKingInYellow_Cover.pdf", interior_pdf="TheKingInYellow_Interior.pdf", page_count=312),
        Book(title="The Kybalion", author="Three Initiates", language="English", price=21.44, description="<i>The Kybalion</i>, attributed to the mysterious “Three Initiates,” presents a concise introduction to Hermetic philosophy and its timeless principles. Drawing on ancient teachings associated with Hermes Trismegistus, it outlines seven fundamental laws governing reality, including mentalism, correspondence, vibration, and polarity. The text emphasizes the power of the mind in shaping experience and encourages disciplined thought as a path to mastery. Accessible yet esoteric, it bridges mysticism and self-development, offering readers tools for understanding both inner and outer worlds. Its enduring appeal lies in its synthesis of spiritual insight and practical guidance for personal transformation.", cover_image="TheKybalion.jpg", cover_pdf="TheKybalion_Cover.pdf", interior_pdf="TheKybalion_Interior.pdf", page_count=149),
        Book(title="Marxism: A Primer", author="Karl Marx & Friedrich Engels", language="English", price=33.46, description="<i>Marxism: A Primer</i> offers a clear and accessible introduction to the key ideas of Karl Marx and his intellectual successors. It explains foundational concepts such as class struggle, historical materialism, surplus value, and the dynamics of capitalism. Designed for newcomers, the text distills complex theory into understandable language while preserving its analytical depth. It also situates Marxism within historical movements and modern debates, highlighting its ongoing relevance. Whether approached as political philosophy or economic critique, this primer equips readers with the tools to engage critically with issues of inequality, labor, and power in contemporary society.", cover_image="Marxism.jpg", cover_pdf="Marxism_Cover.pdf", interior_pdf="Marxism_Interior.pdf", page_count=393),
        Book(title="An Outline of Occult Science", author="Rudolf Steiner", language="English", price=35.54, description="Rudolf Steiner's <i>An Outline of Occult Science</i> presents a comprehensive account of spiritual reality grounded in his system of anthroposophy. The work explores the evolution of the cosmos, humanity, and consciousness through esoteric insight, blending philosophy, mysticism, and imaginative vision. Steiner describes hidden dimensions of existence and the development of the human soul across vast cycles of time. Though complex, the text seeks to reconcile scientific inquiry with spiritual understanding. It invites readers to expand their perception beyond material limits and consider a universe imbued with meaning, purpose, and deeply interconnected layers of being.", cover_image="AnOutlineOfOccultScience.jpg", cover_pdf="AnOutlineOfOccultScience_Cover.pdf", interior_pdf="AnOutlineOfOccultScience_Interior.pdf", page_count=431),
        Book(title="The Revolt of the Masses", author="José Ortega y Gasset", language="English", price=25.58, description="José Ortega y Gasset's <i>The Revolt of the Masses</i> examines the rise of mass society and its impact on culture, politics, and intellectual life. Ortega argues that the dominance of the “mass man,” characterized by conformity and lack of self-discipline, threatens the achievements of civilization. He contrasts this figure with the cultivated individual who strives for excellence and responsibility. The work critiques both democracy's excesses and the erosion of cultural standards, offering a nuanced reflection on modern social dynamics. Provocative and influential, it challenges readers to consider the balance between equality, authority, and the preservation of human greatness.", cover_image="TheRevoltOfTheMasses.jpg", cover_pdf="TheRevoltOfTheMasses_Cover.pdf", interior_pdf="TheRevoltOfTheMasses_Interior.pdf", page_count=232),
    ]
    
    db.session.add_all(books)
    db.session.commit()
    return "Database reseeded."

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)