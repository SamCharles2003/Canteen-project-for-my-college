import schedule
import time
from flask import Flask, render_template, jsonify, request
import pymysql
import threading
import queue

app = Flask(__name__)

# Database connection
conn = pymysql.connect(host='localhost', user='root', password='', database='rfid_data')
cursor = conn.cursor()
@app.route('/')
def webrender():
    transaction_details = live_transaction()
    print([transaction['Name'] for transaction in transaction_details if 'Name' in transaction])
    return render_template('transactions.html', transaction_details=transaction_details)


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






if __name__ == "__main__":
    app.run(host='0.0.0.0', port=8000,debug=True)