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
