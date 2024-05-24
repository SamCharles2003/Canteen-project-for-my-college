import schedule
import time
from flask import Flask, render_template, jsonify, request
import pymysql
import threading
import queue
import base64
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Database connection
conn = pymysql.connect(host='localhost', user='root', password='', database='rfid_data')
cursor = conn.cursor()
@app.route('/')
def webrender():
    food_menu=get_food_menu()
    return render_template('menu_update_page.html', food_menu=food_menu)

def get_food_menu():
    try:
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


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=9900,debug=True)