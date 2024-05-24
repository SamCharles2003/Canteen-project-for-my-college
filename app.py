import schedule
import socket
import time
import serial.win32
from flask import Flask, render_template, jsonify, request, json
import pymysql
import serial
import serial.tools.list_ports
import threading
import queue
import webbrowser
import pywhatkit as pwk
import smtplib
import subprocess
import datetime
import urllib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

db_name = 'rfid_data'

app = Flask(__name__)
########################################AUTONOMUS AND VOLUNTEERING#################################################
try:
    subprocess.call([r"C:\xampp\xampp_start.exe"])
    conn = pymysql.connect(host='localhost', user='root', password='', database='rfid_data')
    cursor = conn.cursor()
except Exception as e:
    print(f"Error: {e}")
except:
    conn = pymysql.connect(host='localhost', user='root', password='')
    cursor = conn.cursor()
    cursor.execute(f"CREATE DATABASE {db_name}")
    print("DB Created")


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


# Function to Start Browser
def open_browser():
    clear_recent_transactions_if_empty()
    host_ip = socket.gethostbyname(socket.gethostname())
    url = f'http://{host_ip}:5000/'
    webbrowser.open(url)


# function to check the recent_transaction table
def clear_recent_transactions_if_empty():
    try:
        # Get today's date in the format 'YYYY-MM-DD'
        today_date = datetime.datetime.now().strftime('%Y-%m-%d')

        # Check if any records exist for today's date
        cursor.execute("SELECT COUNT(*) FROM recent_transactions WHERE `date` = %s", (today_date,))
        record_count = cursor.fetchone()[0]

        if record_count == 0:
            # If no records found, clear the table
            cursor.execute("DELETE FROM `recent_transactions` WHERE 1")
            print(f"Table recent_transactions cleared as no records found for {today_date}")
        else:
            print(f"Records found for {today_date}. Table recent_transactions not cleared.")
    except Exception as e:
        print(f"Error: {e}")


# Start the schedule thread
threading.Thread(target=schedule_thread, daemon=True).start()


#########################################FOOD DISPLAYING,RFID READING,PIN ANALYSING,INFO DISPLAYING<MORE LIKELY RECEIPT PRINTING>####################

# Function to read data from COM port
def read_usb_port(device_name, rfid_tag_queue):
    try:
        # Automatically detect the USB port by device name
        ports = list(serial.tools.list_ports.comports())
        for port, desc, hwid in ports:
            if device_name in desc:
                ser = serial.Serial(port=port, baudrate=9600, timeout=1)
                print(f"Connected to USB port: {port} ({desc})")
                while True:
                    data = ser.readline().decode().strip()  # Read data from USB port
                    if data:
                        print(f"RFID Data received: {data}")
                        rfid_tag_queue.put(data)  # Put RFID data into the queue for processing
                        serial.win32.CloseHandle()
        else:
            print(f"No USB device with name '{device_name}' found.")
    except Exception as e:
        print(f"Error: {e}")


# Function to start reading RFID data in a separate thread
def start_rfid_reading(device_name, rfid_tag_queue):
    threading.Thread(target=read_usb_port, args=(device_name, rfid_tag_queue), daemon=True).start()


# Function to fetch food items from the database and return as a list
def get_food_menu():
    try:
        cursor.execute("SELECT food_name, food_cost , food_quantity , food_type , food_image FROM food_menu")
        food_menu = cursor.fetchall()

        available_food = [{'food_name': row[0], 'food_cost': row[1], 'food_type': row[3], 'food_image': row[4]} for row
                          in food_menu if row[2] > 0]
        unavailable_food = [row[0] for row in food_menu if row[2] <= 0]

        if available_food:
            return available_food
        else:
            return f"{' '.join(unavailable_food)} is currently unavailable"
    except Exception as e:
        print(f"Error fetching food menu: {e}")
        return []


# Route to Menu.html
@app.route('/')
def index():
    food_menu = get_food_menu()  # Fetch food menu from the database
    return render_template('menu.html', food_menu=food_menu)


# Route to Rfid.html
@app.route('/rfid', methods=['GET'])
def rfid():
    return render_template('rfid.html')


# Route to Pin.html
@app.route('/pin', methods=['GET'])
def pin():
    return render_template('pin.html')


# Route to Details.html
@app.route('/details', methods=['GET'])
def details():
    return render_template('details.html')


# checkpoint


# Route to read rfid card<Hardware --SerialPort>
@app.route('/read_com_port', methods=['GET'])
def read_com_port_route():
    device_name = "USB-SERIAL CH340"  # Specify the COM port here
    rfid_tag_queue = queue.Queue()  # Queue to store RFID data
    print("Queue: ", rfid_tag_queue)
    start_rfid_reading(device_name, rfid_tag_queue)  # Start reading RFID data in a separate thread
    # Wait for some time to allow RFID data to be read
    time.sleep(5)
    selected_foods = request.args.get('selected_foods')
    if not selected_foods:
        return jsonify({'success': False, 'message': 'No selected foods provided'})
    # selected_foods_dict = jsonify(selected_foods)
    food_checking = food_check(selected_foods)
    if food_checking != 0:
        if not rfid_tag_queue.empty():
            rfid_tag = rfid_tag_queue.get()
            if check_rfid(rfid_tag) != 1:
                return jsonify({'success': True, 'message': 'not registered', 'rfid_tag': rfid_tag})
            else:
                return jsonify({'success': True, 'message': 'registered', 'rfid_tag': rfid_tag})
        else:
            return jsonify({'success': False, 'message': 'no data'})
    else:
        return jsonify({'success': False, 'message': 'One of the Foods is Unavailable'})


# experimental function
def food_check(selected_food):
    decoded = urllib.parse.unquote(selected_food)
    print("FOOD_CHECK()----->", selected_food)
    return 1


# called Function read_com_port_route to check Availability of Card registered in DB
def check_rfid(rfid_tag):
    try:
        # Assuming 'rfid_tag' is the column name in the 'rfid_data' table
        query = f"SELECT * FROM `rfid_data` WHERE `rfid_tag` = '{rfid_tag}'"
        # Execute the query
        cursor.execute(query)
        # Fetch the result
        result = cursor.fetchone()

        if result:
            # RFID tag exists in the database
            return 1
        else:
            # RFID tag does not exist in the database
            return 0

    except Exception as e:
        print(f"Error: {e}")
        return None


# Route of process_selection API From details.html under POST
@app.route('/process_selection', methods=['POST'])
def process_selection():
    try:

        data = request.json
        selected_foods = data['selected_foods']
        rfid_tag = data.get('rfid_tag')

        cursor.execute(
            f"SELECT name, phone_number, mail_id, current_balance FROM rfid_data WHERE rfid_tag = '{rfid_tag}'")
        rfid_info = cursor.fetchone()

        if rfid_info:
            name, phone_number, mail_id, current_balance = rfid_info
            total_cost = 0

            for food, quantity in selected_foods.items():
                cursor.execute(f"SELECT food_cost FROM food_menu WHERE food_name = '{food}'")
                food_cost = cursor.fetchone()[0]
                total_cost += food_cost * quantity

            if current_balance >= total_cost:
                new_balance = current_balance - total_cost
                cursor.execute(f"UPDATE rfid_data SET current_balance = {new_balance} WHERE rfid_tag = '{rfid_tag}'")
                conn.commit()
                transaction_time = time.strftime("%H:%M:%S")
                transaction_date = time.strftime("%Y-%m-%d")
                update_transaction(name, selected_foods, total_cost, rfid_tag, transaction_date, mail_id)
                update_menu(selected_foods)
                email(rfid_tag, selected_foods, total_cost, new_balance, transaction_time, transaction_date)
                # whatsapp(name,selected_foods,total_cost,new_balance)
                return jsonify({
                    'name': name,
                    'phone_number': phone_number,
                    'mail_id': mail_id,
                    'current_balance': new_balance
                })
            else:
                return jsonify({'message': 'Insufficient balance!'})
        else:
            return jsonify({'message': 'User not found!'})

    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'message': 'Error processing selection.'}), 500


# VOID function of Sending Whatsapp Message
def whatsapp(name, selected_foods, total_cost, new_balance):
    try:
        pwk.sendwhatmsg_instantly(f"+91********",
                                  f"Hi {name}! Your transaction details:\nSelected Foods: {', '.join([f'{food} ({quantity})' for food, quantity in selected_foods.items()])}\nTotal Cost: {total_cost}\nCurrent Balance: {new_balance}",
                                  tab_close=True)
        print("Whatsapp successful")
    except Exception as e:
        print(f"Error: {e}")


# Function Called By process_selection withs args to send email
def email(rfid_tag, selected_foods, total_cost, current_balance, transaction_time, transaction_date):
    try:
        # Fetch email id from the database based on the provided rfid_tag
        cursor.execute(f"SELECT mail_id FROM rfid_data WHERE rfid_tag = '{rfid_tag}'")
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
        message['Subject'] = "Transaction Details"

        # Construct the email body
        email_body = f"""
        <html>
          <head>
            <style>
              body {{
                font-family: 'Arial', sans-serif;
                background-color: #f5f5f5;
                color: #333;
                padding: 20px;
              }}
              .container {{
                max-width: 600px;
                margin: 0 auto;
                background-color: #fff;
                padding: 20px;
                border-radius: 10px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
              }}
              h1 {{
                color: #009688;
              }}
              ul {{
                list-style-type: none;
                padding: 0;
              }}
              li {{
                margin-bottom: 10px;
              }}
            </style>
          </head>
          <body>
            <div class="container">
              <h1>Dear User,</h1>
              <p><strong>Transaction Details:</strong></p>
              <ul>
                <li><strong>Selected Foods:</strong> {', '.join([f'{food} ({quantity})' for food, quantity in selected_foods.items()])}</li>
                <li><strong>Transaction Time:</strong> {transaction_time}</li>
                <li><strong>Transaction Date:</strong> {transaction_date}</li>
                <li><strong>Total Cost:</strong> {total_cost}</li>
                <li><strong>Current Balance:</strong> {current_balance}</li>
              </ul>
            </div>
          </body>
        </html>
        """

        # Attach the email body to the MIME object
        message.attach(MIMEText(email_body, 'html'))

        # Connect to the SMTP server and send the email
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.sendmail(sender_email, recipient_email, message.as_string())

        print("Email sent successfully.")

    except Exception as e:
        print(f"Error sending email: {e}")


# Route for checking pin code with pin_Code API Containing required details
@app.route('/pin_code', methods=['POST'])
def pin_code():
    try:
        data = request.json
        rfid_tag = data.get('rfid_tag')
        user_pin_code = data.get('user_pin_code')

        # Fetch the PIN as a string
        cursor.execute(f"SELECT CAST(pin_number AS CHAR) FROM rfid_data WHERE rfid_tag = '{rfid_tag}'")

        fetched_pin = str(cursor.fetchone()[0])

        print("Incoming RFID", rfid_tag)
        print("Incoming Password", user_pin_code)
        print("Fetched Password", fetched_pin)

        if fetched_pin == user_pin_code:
            return jsonify({'message': 'Authenticated'})
        else:
            return jsonify({'message': 'Not Authenticated'})
    except Exception as e:
        print(f"Error: {e}")
        return jsonify({'message': 'Error processing in Authentication'}), 500


###################################POST PROCESSING PART##############################
# Function called by process_selection with a dictionary as param
def update_menu(selected_foods):
    try:
        print("UPDATE_MENU()--->Control came to Update_menu")
        for food, quantity in selected_foods.items():
            print("UPDATE_MENU()--->Incoming Quantity for Food:", quantity, food)
            per_day_food_ranking(selected_foods)
            cursor.execute(f"SELECT food_quantity FROM food_menu WHERE food_name = '{food}'")
            current_quantity = cursor.fetchone()[0]
            print("UPDATE_MENU()--->Feteched quantity", current_quantity)
            updation_quantity = current_quantity - quantity
            print("UPDATE_MENU()--->Calculated quantity", updation_quantity)
            query = "UPDATE food_menu SET food_quantity = %s WHERE food_name = %s"
            cursor.execute(query, (updation_quantity, food))
            conn.commit()
            print(f"UPDATE_MENU()--->Updating menu for {food} with quantity {quantity}")

        print("UPDATE_MENU()--->Menu successfully updated.")
    except Exception as e:
        print(f"UPDATE_MENU()--->Error: {e}")


# Function called by the process_selection with some params
def update_transaction(name, selected_foods, total_cost, rfid_tag, transaction_date, mail_id):
    try:
        cursor.execute("SELECT MAX(serial_no) FROM recent_transactions")
        result = cursor.fetchone()
        current_serial_number = result[0] if result[0] is not None else 0
        serial_number = current_serial_number + 1
        # Convert the selected_foods dictionary into a string representation
        foods_str = ', '.join([f"{food}-> {quantity}" for food, quantity in selected_foods.items()])
        query = "INSERT INTO `recent_transactions` (`serial_no`, `Name`, `food_name`, `food_cost`,`date`,`mail_id`) VALUES (%s, %s, %s, %s,%s,%s)"
        cursor.execute(query, (serial_number, name, foods_str, total_cost, transaction_date, mail_id))
        conn.commit()
        transaction_history(name, rfid_tag, foods_str, total_cost, transaction_date, serial_number, mail_id)
        transaction_history_graph(transaction_date, total_cost)
        print("Transaction successfully updated.")
    except Exception as e:
        print(f"Error: {e}")


def per_day_food_ranking(selected_foods):
    try:
        for food, quantity in selected_foods.items():
            date = time.strftime("%Y-%m-%d")

            # Check if the entry with the same food and date exists
            cursor.execute("SELECT * FROM `food_sell_history` WHERE `food_name` = %s AND `date` = %s", (food, date))
            existing_entry = cursor.fetchone()

            if existing_entry:
                # If entry exists, update the quantity
                existing_quantity = int(existing_entry[1])  # Assuming 'sell_quantity' is at index 1
                print("PER_DAY_FOOD_RANKING()-->Existing Quantity", existing_quantity)
                new_quantity = int(existing_quantity + quantity)
                print("PER_DAY_FOOD_RANKING()-->New Quantity", new_quantity)
                cursor.execute(
                    "UPDATE `food_sell_history` SET `sell_quantity` = %s WHERE `food_name` = %s AND `date` = %s",
                    (new_quantity, food, date))
            else:
                # If entry doesn't exist, insert a new record
                cursor.execute(
                    "INSERT INTO `food_sell_history`(`food_name`, `sell_quantity`, `date`) VALUES (%s, %s, %s)",
                    (food, quantity, date))

            print("Updated on food_sell_history table")

    except Exception as e:
        print(f"Error: {e}")


def transaction_history(name, rfid_tag, food_str, total_cost, transaction_date, serial_no, mail_id):
    try:
        cursor.execute(
            query="INSERT INTO `transaction_history`(`serial_no`, `rfid_tag`, `name`, `food_name`, `food_cost`, `date`,`mail_id`) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            args=(serial_no, rfid_tag, name, food_str, total_cost, transaction_date, mail_id))
        print("PER_DAY_FOOD_RANKING")
    except Exception as e:
        print(f"Error: {e}")


def transaction_history_graph(transaction_date, total_cost):
    try:
        cursor.execute("SELECT * FROM `transaction_history_graph` WHERE `date` = %s", (transaction_date,))
        existing_entry = cursor.fetchone()

        if existing_entry:
            current_amount = existing_entry[1]
            complete_transaction = current_amount + total_cost
            query = "UPDATE `transaction_history_graph` SET `total_transaction`=%s WHERE `date`=%s"
            cursor.execute(query, args=(complete_transaction, transaction_date))
            print("TRANSACTION_HISTORY_GRAPH")
        else:
            query = "INSERT INTO `transaction_history_graph`(`date`, `total_transaction`) VALUES (%s, %s)"
            cursor.execute(query, args=(transaction_date, total_cost))
            print("TRANSACTION_HISTORY_GRAPH")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    import queue  # Import queue module for managing the RFID data queue

    # Open the browser in a separate thread after a short delay
    threading.Timer(1, open_browser).start()

    app.run(host='0.0.0.0', port=5000, debug=True)
