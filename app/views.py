from flask import render_template, request, session, redirect, url_for, flash
from app import app
from app import models

# Secure User sessions rely on the Secret Key
app.secret_key = app.config['SECRET_KEY']

@app.route('/')
@app.route('/landing')
def landing():
    """Renders the main homepage."""
    return render_template('landing.html')

@app.route('/auth', methods=['GET', 'POST'])
def auth():
    """Handles both GET viewing of the login page, and POST submissions for Login/Signup."""
    
    # If a user is already securely logged in via session, redirect them to the restaurants page
    if 'customer_id' in session:
        return redirect(url_for('restaurants'))

    if request.method == 'POST':
        action = request.form.get('action') # Distinguishes if form was Login or Signup
        
        if action == 'login':
            email = request.form.get('email')
            password = request.form.get('password')
            
            # Query models.py DB function
            user = models.verify_user(email, password)
            if user:
                # Login logic: set securely encypted session cookie
                session['customer_id'] = user['customerId']
                session['user_name'] = user['fname']
                flash('Successfully logged in!', 'success')
                return redirect(url_for('restaurants'))
            else:
                flash('Invalid credentials. Please try again.', 'error')
                
        elif action == 'signup':
            # Collect data from Signup fields
            fname = request.form.get('fname')
            lname = request.form.get('lname', '')
            email = request.form.get('email')
            password = request.form.get('password')
            phone = request.form.get('phone', 'N/A')
            houseName = request.form.get('houseName', 'N/A')
            street = request.form.get('street', 'N/A')
            city = request.form.get('city', 'N/A')
            pincode = request.form.get('pincode', 0)
            
            success = models.create_user(fname, lname, email, password, phone, houseName, street, city, pincode)
            if success:
                flash('Account created! Please log in.', 'success')
            else:
                flash('Error creating account. Email may already exist.', 'error')
                
    return render_template('auth.html')

@app.route('/logout')
def logout():
    """Securely wipes the encrypted session cookie on user logout."""
    session.clear()
    flash('You have been logged out.', 'success')
    return redirect(url_for('landing'))


@app.route('/restaurants')
def restaurants():
    """Fetches all restaurant listings and serves the homedemo.html browse page."""
    if 'customer_id' not in session:
        flash('Please login to view restaurants.', 'error')
        return redirect(url_for('auth'))
    
    restaurant_list = models.get_all_restaurants()
    return render_template('homedemo.html', restaurants=restaurant_list)


@app.route('/menu/<int:restaurant_id>')
def menu(restaurant_id):
    """Fetches targeted DB menu rows for a specific restaurant and passes them into our HTML."""
    if 'customer_id' not in session:
        return redirect(url_for('auth'))
        
    restaurant = models.get_restaurant_by_id(restaurant_id)
    items = models.get_menu_items_by_restaurant(restaurant_id)
    
    # Send variables to Jinja engine inside menu.html
    return render_template('menu.html', restaurant=restaurant, menu_items=items)


@app.route('/cart')
def cart():
    """Requires the user to be active. Computes cart math via Models DB query."""
    if 'customer_id' not in session:
        flash('Please login to view your cart.', 'error')
        return redirect(url_for('auth'))
        
    items = models.get_cart_items(session['customer_id'])
    
    # Calculate cart total quickly in Python 
    cart_total = sum(float(item['totalAmount']) for item in items)
    
    return render_template('cart.html', cart_items=items, total=cart_total)


@app.route('/add_to_cart', methods=['POST'])
def add_cart():
    """Invisible POST route to insert to Cart then reload the menu gracefully."""
    if 'customer_id' not in session:
        return redirect(url_for('auth'))
        
    # Incoming data from HTML Form
    item_id = request.form.get('item_id')
    price = request.form.get('price')
    quantity = int(request.form.get('quantity', 1))
    
    # Map to Real-Time Update Function
    models.add_to_cart(session['customer_id'], item_id, quantity, price)
    
    flash('Item added to cart!', 'success')
    # Use request.referrer to elegantly bump the user exactly back to the menu they were looking at
    return redirect(request.referrer or url_for('restaurants'))


@app.route('/checkout', methods=['POST'])
def checkout():
    """Triggered strictly from the shopping cart. Flushes items and generates the order receipt natively."""
    if 'customer_id' not in session:
        return redirect(url_for('auth'))
        
    # We grab the payment method, defaulting to standard if they bypass the form
    payment_mode = request.form.get('payment_mode', 'Online Transfer')
    
    # Hand the logic off to our secure transaction block
    success, order_id = models.place_order(session['customer_id'], payment_mode)
    
    if success:
        return render_template('orderPlaced.html', order_id=order_id)
    else:
        flash('There was an issue processing your order internally. Please try checking out again.', 'error')
        return redirect(url_for('cart'))
