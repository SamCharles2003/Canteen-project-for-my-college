import schedule
import time
from flask import Flask, render_template, jsonify, request, redirect, url_for, session
import pymysql
import threading
import queue
import base64
import email
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import random
from datetime import datetime, timedelta , timezone
import os
import binascii
from flask import Flask
from flask_cors import CORS,cross_origin


app = Flask(__name__)
#CORS(app,origins=["http://localhost:9900","http://localhost:9900"])  # Enable CORS for all routes
# Generate a random secret key
secret_key = binascii.hexlify(os.urandom(24)).decode('utf-8')
# Set the secret key in your Flask app
app.secret_key = secret_key



# Database connection
conn = pymysql.connect(host='localhost', user='root', password='', database='rfid_data')
cursor = conn.cursor()


def restart_db():
    global conn, cursor
    print("Restarting database connection...")
    conn.close()
    cursor.close()
    conn = pymysql.connect(host='localhost', user='root', password='', database='rfid_data')
    cursor = conn.cursor()

# Autonomous Schedule the database connection restart every 10 seconds
schedule.every(5).seconds.do(restart_db)

# Start the schedule in a separate thread
def schedule_thread():
    while True:
        schedule.run_pending()
        time.sleep(1)

# Start the schedule thread
threading.Thread(target=schedule_thread, daemon=True).start()


################################################ USER SIGN IN AND USER CREDENTIALS RELATED APIs AND FUNCTIONS ########################

@app.route(rule='/',methods=['GET'])
def admin_check():
    return render_template(template_name_or_list='admin_login.html')
@app.route(rule='/check_user', methods=['POST','GET'])
def check_user():
    mesage = ''
    if request.method == 'POST' and 'email' in request.form and 'password' in request.form:
        email = request.form['email']
        password = request.form['password']
        cursor.execute('SELECT * FROM rfid_data WHERE mail_id = % s AND password = % s', (email, password, ))
        user = cursor.fetchone()
        if user:
            session['loggedin'] = True
            session['email'] = user[3]
            mesage = 'Logged in successfully !'
            return redirect(url_for('staff_dashboard', email=user[3]))
        else:
            mesage = 'Please enter correct email / password !'
            return render_template('admin_login.html', mesage = mesage)

@app.route(rule='/forgot_password',methods=['GET'])
def forgot_password():
    return render_template(template_name_or_list='forgot_password.html')

@app.route(rule='/change_password', methods=['POST'])
def change_password():
    try:

        data = request.json
        email= data.get('email')
        cursor.execute( f"SELECT * FROM `rfid_data` WHERE `mail_id` = '{email}'")
        count = cursor.fetchone()
        if count:
            otp = generate_otp()
            session['otp_data'] = {'otp': otp, 'timestamp': datetime.now()}
            session['email'] = email
            session['forget_email'] = email
            email_thread = threading.Thread(target=send_otp_email, args=(email, otp))
            email_thread.start()
            return jsonify({'message': 'success'})


        else:
            return jsonify({ 'message': 'Account was not Found!'})
    except Exception as e:
        return jsonify({'message': 'error', 'error': str(e)})

@app.route(rule='/otp_verification',methods=['GET'])
def otp_verification():
    return render_template(template_name_or_list='otp_verification.html')

@app.route(rule='/verify_otp', methods=['POST'])
def verify_otp():
    print("control Here")
    entered_otp = request.json.get('otp')
    print("Entered OTP",entered_otp)
    print ('otp_data' in session )
    if 'otp_data' in session and 'email' in session:
        print("otp data")
        if not is_otp_session_expired(session['otp_data']['timestamp']):
            stored_otp = session['otp_data']['otp']
            if entered_otp == stored_otp:
                return jsonify({'message': 'success'})
            else:
                return jsonify({'message': 'error'})
    else:
        return jsonify({'message':'timeout'})

    # Add a default return statement in case the conditions are not met

@app.route(rule='/timeout',methods=['GET'])
def timeout():
    return render_template(template_name_or_list='session_closed.html')

@app.route(rule='/update_password',methods=['GET'])
def update_password():
    return render_template(template_name_or_list='change_password.html')

@app.route(rule='/update_password_data', methods=['POST'])
def update_password_data():
    try:
        data = request.json
        email=session['forget_email']
        new_password = data.get('confirmpassword')
        print("UPDATE_PASSWORD_DATA() EMAIL---->",email)
        # Check if the email exists in the database
        cursor.execute(f"SELECT COUNT(*) FROM rfid_data WHERE mail_id = '{email}'")
        count = cursor.fetchone()[0]

        if count > 0:
            # Update the password for the given email
            cursor.execute(f"UPDATE rfid_data SET password = '{new_password}' WHERE mail_id = '{email}'")
            conn.commit()
            confirmation_email_thread = threading.Thread(target=confirmation_email, args=(email,))
            confirmation_email_thread.start()
            return jsonify({'message': 'success'})

        else:

            return  jsonify({'message': 'error', 'error': 'Email not found in the database'})


    except Exception as e:
        print("UPDATE_PASSWORD_DATA()---->ERROR:", e)
        return jsonify({'message': 'error', 'error': str(e)})

def confirmation_email(email):
    try:
        # Fetch email id from the database based on the provided email
        cursor.execute(f"SELECT mail_id FROM rfid_data WHERE mail_id = '{email}'")
        recipient_email = cursor.fetchone()[0]

        # Email configuration (update with your SMTP server details)
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        smtp_username = ""
        smtp_password = ""

        # Sender and recipient email addresses
        sender_email = ""

        # Create a MIME object to represent the email
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = recipient_email
        message['Subject'] = "Password Change Confirmation"

        # Construct the email body
        current_time = time.strftime("%Y-%m-%d %H:%M:%S")
        email_body = f"Dear User,\n\nYour password for the account {email} was changed at {current_time}.\n\nThis change is confirmed.\n\nBest regards,\nYour App Team"

        # Attach the email body to the MIME object
        message.attach(MIMEText(email_body, 'plain'))

        # Connect to the SMTP server and send the email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(sender_email, recipient_email, message.as_string())

        print("Confirmation Email sent successfully.")

    except Exception as e:
        print(f"Error sending email: {e}")

def generate_otp(): 
    return str(random.randint(100000, 999999))

def is_otp_session_expired(timestamp):
    # Make the current time offset-aware
    current_time = datetime.now(timezone.utc)
    # Ensure that the timestamp is offset-aware
    if timestamp.tzinfo is None or timestamp.tzinfo.utcoffset(timestamp) is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return current_time > timestamp + timedelta(minutes=10)

def send_otp_email(email,otp):
    try:
        # Fetch email id from the database based on the provided rfid_tag
        cursor.execute(f"SELECT mail_id FROM rfid_data WHERE mail_id = '{email}'")
        recipient_email = cursor.fetchone()[0]
        # Email configuration (update with your SMTP server details)
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        smtp_username = ""
        smtp_password = ""

        # Sender and recipient email addresses
        sender_email = ""

        # Create a MIME object to represent the email
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = recipient_email
        message['Subject'] = "One Time Password for Account Recovery"

        # Construct the email body
        email_body = f"Dear User,\n\nYour One Time Password for the account {email} is: {otp}\n\nThis OTP is valid for 10 Minutes\nYour App Team"

        # Attach the email body to the MIME object
        message.attach(MIMEText(email_body, 'plain'))

        # Connect to the SMTP server and send the email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(sender_email, recipient_email, message.as_string())
        print("Email Sent Successfully")
        return 1

    except Exception as e:
        print(f"Error sending email: {e}")

@app.route(rule='/sign_up',methods=['GET'])
def sign_up():
    return render_template('sign_up.html')

from flask import jsonify

@app.route(rule='/signupdata', methods=['POST'])
def signupdata():
    try:
        data = request.json
        name = data.get('firstName')
        email = data.get('email')
        password = data.get('password')
        phoneNumber = data.get('phoneNumber')
        userType = data.get('userType')
        otp=data.get('otp')
        print("SIGNUPDATA()--->Entered OTP", otp)
        print('SIGNUPDATA()--->otp_data' in session)
        if 'otp_data' in session and 'email' in session:
            print("otp data")
            if not is_otp_session_expired(session['otp_data']['timestamp']):
                stored_otp = session['otp_data']['otp']
                if otp == stored_otp:
                    cursor.execute(
                        "INSERT INTO rfid_data (name, mail_id, password, phone_number,user_type) VALUES (%s, %s, %s, %s,%s)",
                        (name, email, password, phoneNumber, userType))
                    return jsonify({'message': 'success'})
                else:
                    return jsonify({'message': 'error'})
        else:
            return jsonify({'message': 'timeout'})




    except Exception as e:
        return jsonify({'message': 'error', 'error': str(e)})

@app.route(rule='/logout',methods=['GET'])
def logout():
    session['loggedin'] = False
    session['email'] = ""
    print("Successfully Looged Outx`")
    return render_template(template_name_or_list='admin_login.html')

@app.route(rule='/signup_otp',methods=['POST'])
def signup_otp():
    try:
        print("Control in signup_otp")
        data=request.json
        email = data.get('email')
        cursor.execute("SELECT * FROM `rfid_data` WHERE `mail_id` = %s",args=(email,))
        existence=cursor.fetchall()[0]
        if existence:
            otp = generate_otp()
            session['otp_data'] = {'otp': otp, 'timestamp': datetime.now()}
            session['email'] = email
            email_thread = threading.Thread(target=signup_send_otp_email, args=(email, otp))
            email_thread.start()
            if True:
                return jsonify({'message': 'success'})
            else:
                return jsonify({'message': 'error'})
        else:
            return jsonify({'message':"This User is Already Taken !"})
    except Exception as e:
        return jsonify({'message':'error'})
        print("SIGNUP_OTP----> Error:",e)


def signup_send_otp_email(email,otp):
    try:
        recipient_email=email
        smtp_server = "smtp.gmail.com"
        smtp_port = 587
        smtp_username = ""
        smtp_password = ""

        # Sender and recipient email addresses
        sender_email = ""

        # Create a MIME object to represent the email
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = recipient_email
        message['Subject'] = "One Time Password for SignUp Account"

        # Construct the email body
        email_body = f"Dear User,\n\nYour One Time Password for the account {email} is: {otp}\n\nThis OTP is valid for 10 Minutes\nYour App Team"

        # Attach the email body to the MIME object
        message.attach(MIMEText(email_body, 'plain'))

        # Connect to the SMTP server and send the email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(sender_email, recipient_email, message.as_string())
        print("Email Sent Successfully")
        return 1

    except Exception as e:
        print(f"Error sending email: {e}")


############################################## STAFF WINDOW API AND FUNCTIONS ############################

@app.route(rule='/menu_update',methods=['GET'])
def menu_update():
    food_menu=get_food_menu()
    return render_template('menu_update_page.html', food_menu=food_menu)

def get_food_menu():
    try:
        print("get_food_menu was Summoned")
        cursor.execute("SELECT food_name, food_cost, food_quantity , food_image FROM food_menu")
        food_menu = cursor.fetchall()
        print(" Decoded image ", 'food_image' in food_menu )
        return [
            {
                'food_name': row[0],
                'food_cost': row[1],
                'food_quantity': row[2],
                'food_image': row[3]
            }
            for row in food_menu
        ]
    except Exception as e:
        print(f"Error fetching food menu: {e}")
        return []

@app.route('/deletion', methods=['POST'])
def deletion():
    try:
        data = request.json
        selected_food = data['selected_food']  # Update the parameter name here
        if selected_food != '':
            cursor.execute(f"DELETE FROM food_menu WHERE food_name ='{selected_food}';")
            conn.commit()
            return jsonify({'message': 'done'})
        else:
            return jsonify({'message': 'error'})
    except Exception as e:
        return jsonify({'message': f'error: {str(e)}'})

@app.route('/updation', methods=['POST'])
def updation():
    try:
        data = request.json
        selected_food = data['foodName']
        args = data['quantity_value']
        print(selected_food, args)

        # Use parameterized query to avoid SQL injection
        query = "UPDATE food_menu SET food_quantity = %s WHERE food_name = %s"
        cursor.execute(query, (args, selected_food))
        conn.commit()
        #print(cursor._last_executed)
        return jsonify({'message': 'successfully Updated'})

    except Exception as e:
        return jsonify({'message': f'error: {str(e)}'})

@app.route('/menuupdation', methods=['POST'])
def menuupdation():
    try:
        data = request.form
        food_name = data.get('update_food_name')
        food_cost = data.get('update_food_cost')
        food_quantity = data.get('update_food_quantity')
        food_type = data.get('update_food_type')
        food_image = request.files.get('update_food_image')
        print(food_image)

        print("Received data:", food_name, food_cost, food_quantity ,food_type,food_image)
        if food_image:
            # Read the content of the image file
            image_data = food_image.read()
            # Encode the image data in base64
            encoded_image = base64.b64encode(image_data).decode('utf-8')
            print("Image Encoded!",encoded_image)
        else:
            # If no image is provided, set it to None
            encoded_image = None


        query = "INSERT INTO `food_menu` (`food_name`, `food_cost`, `food_quantity` , `food_type` , `food_image`) VALUES (%s, %s, %s,%s,%s)"
        cursor.execute(query, (food_name, food_cost, food_quantity,food_type,encoded_image))
        conn.commit()
        print("Menu push done")

        return jsonify({'message': 'success', 'new_quantity': food_quantity})

    except Exception as e:
        return jsonify({'message': f'error: {str(e)}'})

@app.route(rule='/live_transaction',methods=['GET'])
def live_transaction():
    transaction_details = live_transaction()
    print([transaction['Name'] for transaction in transaction_details if 'Name' in transaction])
    return render_template('transactions.html', transaction_details=transaction_details)

@app.route(rule='/search', methods=['POST'])
def search():
    
    try:
        data = request.json
        searchterm = data['searchterm']
        mode = data['mode']

        if mode == 'rfid':
            cursor.execute("SELECT  `name`, `phone_number`, `mail_id`, `current_balance`, `status`, `user_type` FROM `rfid_data` WHERE `rfid_tag`=%s", args=(searchterm,))
        elif mode == 'registernumber':
            cursor.execute("SELECT  `name`, `phone_number`, `mail_id`, `current_balance`, `status`, `user_type` FROM `registernumber_data` WHERE `register_number`=%s", args=(searchterm,))
        elif mode == 'email':
            cursor.execute("SELECT  `name`, `phone_number`, `mail_id`, `current_balance`, `status`, `user_type` FROM `email_data` WHERE `email`=%s", args=(searchterm,))
        elif mode == 'phonenumber':
            cursor.execute("SELECT  `name`, `phone_number`, `mail_id`, `current_balance`, `status`, `user_type` FROM `phonenumber_data` WHERE `phone_number`=%s", args=(searchterm,))
        else:
            return jsonify({'message': 'error', 'results': 'Invalid mode'})

        fetched_data = cursor.fetchall()
        print("FROM SEARCH()--->", fetched_data)

        return jsonify({'message': 'success', 'results': fetched_data})

    except Exception as e:
        print("FROM SEARCH()--->ERROR:", e)
        return jsonify({'message': 'error', 'results': 'An error occurred'})


def live_transaction():
    try:

        cursor.execute("SELECT `serial_no`, `Name`, `food_name`, `food_cost` FROM `recent_transactions` ORDER BY `serial_no` DESC LIMIT 10000")
        conn.commit()
        transaction_data=cursor.fetchall()

        return [{'serial_no': row[0], 'Name': row[1], 'food_name': row[2], 'food_cost': row[3]} for row in
                transaction_data]
    except Exception as e:
        print(f"Error: {e}")
        return []


def debit_balance():
    try:
        cursor.execute("SELECT SUM(current_balance) AS total_balance FROM `rfid_data` ")
        current_balance=cursor.fetchone()[0]
        return current_balance
    except Exception as e:
        print("ERROR:From debit_balance()---->",e)


def current_transaction():
    try:
        date = time.strftime("%Y-%m-%d")
        cursor.execute("SELECT * FROM `transaction_history_graph` WHERE `date`= %s",(date,))
        transaction_amount=cursor.fetchone()[1]
        return transaction_amount
    except Exception as e:
        print("ERROR:From current_transaction()--->",e)


def menu_graph():
    try:
        date=time.strftime("%Y-%m-%d")
        cursor.execute("SELECT * FROM `food_sell_history` WHERE `date`= %s",(date,))
        temporary=cursor.fetchall()
        food_sell_number=[{"sell_quantity":row[1],"food_name":row[0]}for row in temporary]
        print(food_sell_number)
        return food_sell_number
    except Exception as e:
        print("ERROR:From Menu_graph--->",e)


def transaction_graph():
    try:
        cursor.execute("SELECT * FROM `transaction_history_graph` WHERE 1")
        temporary=cursor.fetchall()
        transaction_graph_values = [{"total_transaction": row[1], "date": row[0]} for row in temporary]
        return transaction_graph_values
    except Exception as e:
        print("ERROR:From Transaction_graph()--->",e)


@app.route('/staff_dashboard', methods=['GET'])
def staff_dashboard():
    # Check if the user is logged in
    if 'loggedin' in session and session['loggedin']:
        email = session.get('email', None)  # Get the email from the session
        cursor.execute("SELECT `name`FROM `rfid_data` WHERE `mail_id`= %s",(email,))
        name=cursor.fetchone()[0]
        if email:
            debit_balance_value = debit_balance()
            current_transaction_value = current_transaction()
            menu_graph_value = menu_graph()
            transaction_graph_value = transaction_graph()
            print(transaction_graph_value)
            return render_template('staff_dashboard.html',
                                   debit_balance_value=debit_balance_value,
                                   current_transaction_value=current_transaction_value,
                                   menu_graph_value=menu_graph_value,
                                   transaction_graph_value=transaction_graph_value,
                                   email=email,
                                   name=name)
        else:
            # Handle case where email is not in the session
            return redirect(url_for('admin_check'))  # Redirect to login page
    else:
        # Handle case where user is not logged in
        return redirect(url_for('admin_check'))








if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5500,debug=True)
