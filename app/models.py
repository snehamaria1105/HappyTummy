import mysql.connector
from app import app
from werkzeug.security import generate_password_hash, check_password_hash

def get_db_connection():
    """ 
    Safely spins up a connection using the protected credentials in config.py.
    """
    return mysql.connector.connect(
        host=app.config['DB_HOST'],
        user=app.config['DB_USER'],
        password=app.config['DB_PASSWORD'],
        database=app.config['DB_NAME']
    )

def get_all_restaurants():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM RESTAURANT")
    restaurants = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return restaurants

def get_restaurant_by_id(restaurant_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM RESTAURANT WHERE restaurantId = %s", (restaurant_id,))
    restaurant = cursor.fetchone()
    
    cursor.close()
    conn.close()
    return restaurant

def get_menu_items_by_restaurant(restaurant_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM MENU_ITEMS WHERE restaurantId = %s", (restaurant_id,))
    items = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return items

def create_user(fname, lname, email, password, phone, houseName, street, city, pincode, midname=''):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Important: Never store raw passwords! Mask it securely before inserting it into MySQL.
    hashed_pw = generate_password_hash(password)
    
    sql = """
        INSERT INTO CUSTOMER (fname, lname, midname, email, password, phone, houseName, street, city, pincode)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    
    # We pass variables as a trailing tuple securely preventing SQL Injection Hacks!
    val = (fname, lname, midname, email, hashed_pw, phone, houseName, street, city, pincode)
    
    try:
        cursor.execute(sql, val)
        conn.commit()
        success = True
    except mysql.connector.Error as err:
        print(f"Database Error: {err}")
        success = False
    finally:
        cursor.close()
        conn.close()
        
    return success

def verify_user(email, password):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    sql = "SELECT * FROM CUSTOMER WHERE email = %s"
    cursor.execute(sql, (email,))
    user = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    # Check if user object exists AND the password physically matches the hashed one in the database
    if user and check_password_hash(user['password'], password):
        return user
    return None

def add_to_cart(customer_id, item_id, quantity, price):
    total_amount = float(quantity) * float(price)
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # First, verify if item is already in their active cart
    cursor.execute("SELECT * FROM CART WHERE customerId = %s AND itemId = %s", (customer_id, item_id))
    existing = cursor.fetchone()
    
    if existing:
        # If yes, seamlessly increment the quantity and totalAmount inline
        sql = "UPDATE CART SET quantity = quantity + %s, totalAmount = totalAmount + %s WHERE customerId = %s AND itemId = %s"
        val = (quantity, total_amount, customer_id, item_id)
    else:
        # If no, execute a raw INSERT
        sql = "INSERT INTO CART (customerId, itemId, quantity, totalAmount) VALUES (%s, %s, %s, %s)"
        val = (customer_id, item_id, quantity, total_amount)
        
    cursor.execute(sql, val)
    conn.commit()
    cursor.close()
    conn.close()

def get_cart_items(customer_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # A powerful JOIN linking the user's numeric `itemId` internally against `MENU_ITEMS` to scrape names and images
    sql = """
        SELECT c.cartId, c.quantity, c.totalAmount, m.itemName, m.price, m.imageurl, m.itemId, m.restaurantId
        FROM CART c
        JOIN MENU_ITEMS m ON c.itemId = m.itemId
        WHERE c.customerId = %s
    """
    cursor.execute(sql, (customer_id,))
    cart_items = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return cart_items

def get_user_info(customer_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM CUSTOMER WHERE customerId = %s", (customer_id,))
    user_info = cursor.fetchone()
    
    cursor.close()
    conn.close()
    return user_info

def get_order_history(customer_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Grab main orders sorted by latest, pulling explicit restaurant metadata safely
    sql = """
        SELECT o.orderId, o.timestamp, o.totalAmount, o.status, o.restaurantId, r.restaurantName
        FROM ORDERS o
        JOIN RESTAURANT r ON o.restaurantId = r.restaurantId
        WHERE o.customerId = %s
        ORDER BY o.timestamp DESC
    """
    cursor.execute(sql, (customer_id,))
    orders = cursor.fetchall()
    
    # For each order, fetch items string grouped
    for order in orders:
        item_sql = """
            SELECT m.itemName, od.quantity
            FROM ORDER_DETAILS od
            JOIN MENU_ITEMS m ON od.itemId = m.itemId
            WHERE od.orderId = %s
        """
        cursor.execute(item_sql, (order['orderId'],))
        items = cursor.fetchall()
        
        # Build string "Margherita x1, Coke x2" dynamically
        item_strings = [f"{it['itemName']} x{it['quantity']}" for it in items]
        order['items_summary'] = ", ".join(item_strings)
        
        # Pull any existing review for this exact restaurant by this exact user
        review_sql = """
            SELECT rating, reviewText 
            FROM RATING 
            WHERE customerId = %s AND restaurantId = %s
            LIMIT 1
        """
        cursor.execute(review_sql, (customer_id, order['restaurantId']))
        existing_review = cursor.fetchone()
        
        if existing_review:
            order['existing_rating'] = existing_review['rating']
            order['existing_review'] = existing_review['reviewText']
        else:
            order['existing_rating'] = None
        
    cursor.close()
    conn.close()
    return orders

def get_order_receipt(order_id, customer_id):
    """Deeply inspects an explicit transaction dynamically returning cleanly nested invoice datasets mapping all 4 required tables!"""
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    sql = """
        SELECT o.orderId, o.timestamp, o.totalAmount as orderTotal, o.status,
               b.mode as paymentMode, b.billingId,
               c.fname, c.lname, c.phone, c.houseName, c.street, c.city, c.pincode,
               r.restaurantName, r.location
        FROM ORDERS o
        LEFT JOIN BILLING b ON o.orderId = b.orderId
        JOIN CUSTOMER c ON o.customerId = c.customerId
        JOIN RESTAURANT r ON o.restaurantId = r.restaurantId
        WHERE o.orderId = %s AND o.customerId = %s
    """
    cursor.execute(sql, (order_id, customer_id))
    receipt = cursor.fetchone()
    
    if not receipt:
        cursor.close()
        conn.close()
        return None
        
    # Inject exact granular line-items 
    item_sql = """
        SELECT m.itemName, od.quantity, od.price 
        FROM ORDER_DETAILS od
        JOIN MENU_ITEMS m ON od.itemId = m.itemId
        WHERE od.orderId = %s
    """
    cursor.execute(item_sql, (order_id,))
    receipt['order_items'] = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return receipt

def submit_review(customer_id, restaurant_id, rating, review_text):
    """Safely drops granular customer feedback permanently mapped back explicitly to their Restaurant Entity natively hitting the existing scale RATING schema"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Block redundant duplications preventing user-spam by intelligently transforming duplicates natively into Upserts
    cursor.execute("SELECT ratingId FROM RATING WHERE customerId = %s AND restaurantId = %s LIMIT 1", (customer_id, restaurant_id))
    if cursor.fetchone():
        sql = "UPDATE RATING SET rating = %s, reviewText = %s WHERE customerId = %s AND restaurantId = %s"
        cursor.execute(sql, (rating, review_text, customer_id, restaurant_id))
    else:
        sql = """
            INSERT INTO RATING (customerId, restaurantId, rating, reviewText)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(sql, (customer_id, restaurant_id, rating, review_text))
        
    conn.commit()
    cursor.close()
    conn.close()

def update_cart_quantity(customer_id, cart_id, action):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Needs to get unit price from MENU_ITEMS to safely increment 'totalAmount' by exactly 1 unit's price
    sql = """
        SELECT c.quantity, c.totalAmount, m.price 
        FROM CART c
        JOIN MENU_ITEMS m ON c.itemId = m.itemId
        WHERE c.cartId = %s AND c.customerId = %s
    """
    cursor.execute(sql, (cart_id, customer_id))
    row = cursor.fetchone()
    if not row:
        return
        
    qty, total_amt, unit_price = row
    
    if action == 'increase':
        qty += 1
        total_amt += unit_price
        cursor.execute("UPDATE CART SET quantity = %s, totalAmount = %s WHERE cartId = %s", (qty, total_amt, cart_id))
    elif action == 'decrease':
        if qty > 1:
            qty -= 1
            total_amt -= unit_price
            cursor.execute("UPDATE CART SET quantity = %s, totalAmount = %s WHERE cartId = %s", (qty, total_amt, cart_id))
        else:
            # If they hit 0, remove it entirely
            cursor.execute("DELETE FROM CART WHERE cartId = %s", (cart_id,))
    elif action == 'remove':
        cursor.execute("DELETE FROM CART WHERE cartId = %s", (cart_id,))
        
    conn.commit()
    cursor.close()
    conn.close()


def place_order(customer_id, payment_mode):
    """
    This is an advanced highly-secure MySQL Transaction block. 
    It executes 5 steps successively, and rolls back EVERY change instantly if anything fails, preventing stray data!
    """
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Step 1: Query all current cart items directly from DB to prevent client-side cart spoofing
        sql = """
            SELECT c.quantity, c.totalAmount, m.itemId, m.price, m.restaurantId
            FROM CART c
            JOIN MENU_ITEMS m ON c.itemId = m.itemId
            WHERE c.customerId = %s
        """
        cursor.execute(sql, (customer_id,))
        cart_items = cursor.fetchall()
        
        if not cart_items:
            raise Exception("Cart is completely empty!")
            
        # Securely recalculate the total amount server-side 
        # (We assume an order binds to the restaurant of the primary item based on schema constraints)
        total_order_amount = sum(float(item['totalAmount']) for item in cart_items)
        restaurant_id = cart_items[0]['restaurantId']
        
        from datetime import datetime
        now = datetime.now()
        
        # Step 2: Log into ORDERS table
        order_sql = """
            INSERT INTO ORDERS (timestamp, totalAmount, status, customerId, restaurantId)
            VALUES (%s, %s, %s, %s, %s)
        """
        cursor.execute(order_sql, (now, total_order_amount, 'Preparing', customer_id, restaurant_id))
        order_id = cursor.lastrowid # Grabs the auto-increment ID to link subsequent tables precisely!
        
        # Step 3: Iterate through cart and map rows individually into ORDER_DETAILS table
        for item in cart_items:
            detail_sql = """
                INSERT INTO ORDER_DETAILS (quantity, price, itemId, orderId)
                VALUES (%s, %s, %s, %s)
            """
            cursor.execute(detail_sql, (item['quantity'], item['price'], item['itemId'], order_id))
            
        # Step 4: Construct the final BILLING receipt sequence record
        billing_sql = """
            INSERT INTO BILLING (orderId, mode, totalAmount, timestamp)
            VALUES (%s, %s, %s, %s)
        """
        cursor.execute(billing_sql, (order_id, payment_mode, total_order_amount, now))
        
        # Step 5: Beautifully wipe out the user's cart since they paid
        clear_cart_sql = "DELETE FROM CART WHERE customerId = %s"
        cursor.execute(clear_cart_sql, (customer_id,))
        
        # Important: Lock and finalize the transaction to Database only once ALL lines execute securely!
        conn.commit()
        return True, order_id
        
    except Exception as e:
        print(f"Transaction Order Error: {e}")
        # Panic mode: Revert all incomplete DB rows instantly if it crashes anywhere (like if their card declined)
        conn.rollback() 
        return False, None
    finally:
        cursor.close()
        conn.close()
