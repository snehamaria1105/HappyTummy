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
        SELECT c.cartId, c.quantity, c.totalAmount, m.itemName, m.price, m.imageurl, m.itemId
        FROM CART c
        JOIN MENU_ITEMS m ON c.itemId = m.itemId
        WHERE c.customerId = %s
    """
    cursor.execute(sql, (customer_id,))
    cart_items = cursor.fetchall()
    
    cursor.close()
    conn.close()
    return cart_items
