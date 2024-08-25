from flask import Flask, render_template, request, url_for, redirect, session, make_response, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
import requests
import json
import xmltodict
from datetime import datetime
from flask import jsonify
from flask_socketio import SocketIO
from sqlalchemy.exc import SQLAlchemyError



app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rate.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'lanre'
app.config['DEBUG'] = True

socketio = SocketIO(app)
db = SQLAlchemy(app)

# Track unique client session IDs
connected_clients = set()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    user_id = db.Column(db.String(36), unique=True, nullable=True)  #user id column

    def update_profile(self, new_username, new_password):
        self.username = new_username
        if new_password:
            self.password = new_password
        db.session.commit()

class ProposedTrip(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), nullable=False)
    trip_id = db.Column(db.String(36), unique=True, nullable=False)
    location = db.Column(db.String(100), nullable=False)
    date = db.Column(db.String(20), nullable=False)
    weather = db.Column(db.String(2000), nullable=False)
    interest_count = db.Column(db.Integer, default=0)

class Interest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(36), db.ForeignKey('user.user_id'), nullable=False)
    expressing_user_id = db.Column(db.String(36), nullable=False)
    trip_id = db.Column(db.String(36), db.ForeignKey('proposed_trip.trip_id'), nullable=False)
    accepted = db.Column(db.Boolean, default=False)




def generate_trip_id():
    # Generating a random trip id using the random API

    api_url = 'https://www.randomnumberapi.com/api/v1.0/uuid?'
    response = requests.get(api_url)
    ids = response.json()
    return ids[0] if ids else None

@socketio.on('connect')
def handle_connect():
    if request.sid not in connected_clients:
        connected_clients.add(request.sid)
        print(f'Client connected: {request.sid}')


@socketio.on('disconnect')
def handle_disconnect():
    # Remove the client session ID from the set on disconnect
    if request.sid in connected_clients:
        connected_clients.remove(request.sid)
        print(f'Client disconnected: {request.sid}')

@socketio.on('message_from_client')
def handle_message(data):
    print(f'Message from client {request.sid}: {data}')
    # Broadcast the message to all connected clients
    socketio.emit('message_from_server', {'sid': request.sid, 'message': data})





@app.route('/searchResults', methods=['GET', 'POST'])
def search_trips():
    try:
        if request.method == 'POST':
            # Query the database for trips based on the location
            location = request.form.get('search_location')
            user_id = session.get('user_id')

            # query to exclude trips proposed by the current user
            trips = ProposedTrip.query.filter(ProposedTrip.location == location).all()
            trips = [trip for trip in trips if trip.user_id != user_id]

            return render_template('searchResults.html', trips=trips, search_location=location)
        elif request.method == 'GET':
            # Handle GET requests
            return render_template('searchResults.html', trips=[], search_location=None)
    except SQLAlchemyError as db_error:
        # Handle SQLAlchemy database-related errors
        db.session.rollback()  # Rollback any pending database transactions
        error_message = f"Database error: {str(db_error)}"
        app.logger.error(error_message)  # Log the error
        return render_template('error.html', error=error_message)
    except Exception as e:
        # Handle other general exceptions
        error_message = f"An unexpected error occurred: {str(e)}"
        app.logger.error(error_message)  # Log the error
        return render_template('error.html', error=error_message)
@app.route('/')
def home():
    return render_template('login.html')



@app.route('/chat')
def chat():
    return render_template('chatClient.html')

@app.route('/go_to_chat', methods=['POST'])
def go_to_chat():
    username = request.form.get('username')
    # Process the username and perform any necessary actions

    return render_template('chatClient.html', username=username)

@app.route('/registerPage', methods=['GET', 'POST'])
def runRegister():
    try:
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']

            # Fetch random IDs from the API
            api_url = 'https://www.randomnumberapi.com/api/v1.0/uuid?'
            response = requests.get(api_url)
            ids = response.json()

            # Take the first random ID from the list (if available)
            user_id = ids[0] if ids else None

            new_user = User(username=username, password=password, user_id=user_id)
            db.session.add(new_user)
            db.session.commit()

            return redirect(url_for('runLogin'))

        return render_template('register.html')
    except SQLAlchemyError as db_error:
        # Handle SQLAlchemy database-related errors
        db.session.rollback()  # Rollback any pending database transactions
        error_message = f"Database error: {str(db_error)}"
        app.logger.error(error_message)  # Log the error
        return render_template('error.html', error=error_message)
    except Exception as e:
        # Handle other general exceptions
        error_message = f"An unexpected error occurred: {str(e)}"
        app.logger.error(error_message)  # Log the error
        return render_template('error.html', error=error_message)

@app.route('/edit_profile', methods=['GET', 'POST'])
def edit_profile():
    try:
        if request.method == 'POST':
            new_username = request.form.get('new_username')
            new_password = request.form.get('new_password')

            # Fetch user from session
            user_id = session.get('user_id')
            user = User.query.filter_by(user_id=user_id).first()

            if user:
                # Check if the new username already exists
                existing_user = User.query.filter(User.username == new_username, User.user_id != user_id).first()

                if existing_user:
                    flash('Username already exists. Please choose a different one.', 'error')
                    return redirect(url_for('edit_profile'))

                # Update the profile if the new username is unique
                user.update_profile(new_username, new_password)
                flash('Profile updated successfully.', 'success')

                # Fetch the updated user information
                updated_user = User.query.filter_by(user_id=user_id).first()

                # Pass the updated information to index.html
                return render_template('index.html', username=updated_user.username, user_id=updated_user.user_id)

            # Fetch user from session for GET requests
        user_id = session.get('user_id')
        user = User.query.filter_by(user_id=user_id).first()

        return render_template('editProfile.html', user=user)

    except SQLAlchemyError as db_error:
        # Handle SQLAlchemy database-related errors
        db.session.rollback()  # Rollback any pending database transactions
        error_message = f"Database error: {str(db_error)}"
        app.logger.error(error_message)  # Log the error
        return render_template('error.html', error=error_message)
    except Exception as e:
        # Handle other general exceptions
        error_message = f"An unexpected error occurred: {str(e)}"
        app.logger.error(error_message)  # Log the error
        return render_template('error.html', error=error_message)


@app.route('/validate_current_password', methods=['POST'])
def validate_current_password():
    try:
        data = request.json
        current_password = data.get('current_password')

        # Fetch user from session
        user_id = session.get('user_id')
        user = User.query.filter_by(user_id=user_id).first()

        if user and user.password == current_password:
            return "valid", 200
        else:
            return "invalid", 401

    except Exception as e:
        app.logger.error(f"Wrong Current Password: {str(e)}")
        return "error", 500



@app.route('/delete_account')
def delete_account():
    return render_template('delete_account.html')

@app.route('/confirm_delete_account', methods=['POST'])
def confirm_delete_account():
    try:
        # Fetch user from session
        user_id = session.get('user_id')

        #applies a filter to the query to find a user whose user_id matches the user_id retrieved from the session.
        user = User.query.filter_by(user_id=user_id).first()

        if user:
            # Perform any additional cleanup or tasks before deleting the account
            # For example, you might want to delete associated records in other tables

            # Delete the user account
            db.session.delete(user)
            db.session.commit()

            # Clear the session and redirect to the confirmation page
            session.clear()
            return redirect(url_for('runRegister'))

    except SQLAlchemyError as db_error:
        db.session.rollback()
        error_message = f"Database error: {str(db_error)}"
        app.logger.error(error_message)
        return render_template('error.html', error=error_message)

    except Exception as e:
        error_message = f"An unexpected error occurred: {str(e)}"
        app.logger.error(error_message)
        return render_template('error.html', error=error_message)

    return redirect(url_for('runIndex'))


@app.route('/geolocation')
def geolocation():
    return render_template('geolocation.html')

# New route to handle the acceptance of trip interests
@app.route('/acceptInterest/<interest_id>', methods=['POST'])
def accept_interest(interest_id):
    try:
        # Fetches the interest from the database based on interest_id
        interest = db.session.query(Interest).get(interest_id)

        if not interest:
            return jsonify({'error': 'Interest not found.'}), 404

        # Mark the interest as accepted
        interest.accepted = True
        db.session.commit()

        # Emit a SocketIO event to notify the expressing user
        expressing_user_id = interest.expressing_user_id
        socketio.emit('interest_accepted', {'expressing_user_id': expressing_user_id}, room=expressing_user_id)

        return jsonify({'message': 'Interest accepted successfully.'}), 200

    except SQLAlchemyError as db_error:
        # Handle SQLAlchemy database-related errors
        db.session.rollback()  # Rollback any pending database transactions
        error_message = f"Database error: {str(db_error)}"
        app.logger.error(error_message)  # Log the error
        return jsonify({'error': error_message}), 500
    except Exception as e:
        # Handle other general exceptions
        error_message = f"An unexpected error occurred: {str(e)}"
        app.logger.error(error_message)  # Log the error
        return jsonify({'error': error_message}), 500
@app.route('/loginpage', methods=['GET', 'POST'])
def runLogin():
    try:
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']

            user = User.query.filter_by(username=username, password=password).first()
            if user:
                # Store username and user_id in the session
                session['username'] = username
                session['user_id'] = user.user_id

                return redirect(url_for('runIndex'))
            else:
                flash('Invalid username or password. Please try again.', 'error')
                return redirect(url_for('runLogin'))

        return render_template('login.html')

    except SQLAlchemyError as db_error:
        # Handle SQLAlchemy database-related errors
        error_message = f"Database error: {str(db_error)}"
        app.logger.error(error_message)  # Log the error
        return render_template('error.html', error_message=error_message), 500
    except Exception as e:
        # Handle other general exceptions
        error_message = f"An unexpected error occurred: {str(e)}"
        app.logger.error(error_message)  # Log the error
        return render_template('error.html', error_message=error_message), 500

def fetch_user_by_id(user_id):
    user = User.query.filter_by(user_id=user_id).first()
    return user


@app.route('/index')
def runIndex():
    # Fetch username and random ID from session
    username = session.get('username')
    user_id = session.get('user_id')

    return render_template('index.html', username=username, user_id=user_id)



@app.route('/query', methods=['GET', 'POST'])
def query():
    if request.method == 'POST':
        location = request.form.get('search_location')
        # Query the database for trips based on the location
        trips = ProposedTrip.query.filter_by(location=location).all()
        return render_template('searchResults.html', trips=trips, search_location=location)

        # Render the query.html template for GET requests
    return render_template('query.html')


@app.route('/proposedTrips', methods=['GET', 'POST'])
def proposed_trips():
    try:
        if request.method == 'POST':
            user_id = session.get('user_id')
            trip_id = generate_trip_id()
            location = request.form['location']
            date = request.form['start_date']

            # Fetch weather here
            base_url = f'https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{location}/{date}/{date}?unitGroup=metric&key=P26NNPL4J95PEE2W5RCGSLPYR&contentType=json'
            resp = requests.get(base_url)

            if resp.status_code == 200:
                weather_data = resp.json().get('days', [])
                weather_info = []  # New list to store weather information

                for day in weather_data:
                    date = day.get('datetime')
                    avg_temp = day.get('temp', 0)
                    condition = day.get('conditions')
                    max_temp = day.get('tempmax', 0)
                    min_temp = day.get('tempmin', 0)
                    weather_info.append({
                        'date': date,
                        'avg_temp': avg_temp,
                        'condition': condition,
                        'max_temp': max_temp,
                        'min_temp': min_temp
                    })

                # Save values to session
                session['proposed_trip_id'] = trip_id
                session['proposed_location'] = location
                session['proposed_date'] = date
                session['proposed_weather'] = weather_info  # Update to use the weather_info list

                # Convert the weather_info list to a JSON string
                weather_info_json = json.dumps(weather_info)

                with app.app_context():
                    new_trip = ProposedTrip(user_id=user_id, trip_id=trip_id, location=location, date=date,
                                            weather=json.dumps(weather_info))
                    db.session.add(new_trip)
                    db.session.commit()

                return redirect(url_for('proposed_tripsDetails'))

            return f"Error: {resp.status_code}"

        return render_template('proposeTrip.html')

    except SQLAlchemyError as db_error:
        # Handle SQLAlchemy database-related errors
        error_message = f"Database error: {str(db_error)}"
        app.logger.error(error_message)  # Log the error
        return render_template('error.html', error_message=error_message), 500
    except Exception as e:
        # Handle other general exceptions
        error_message = f"An unexpected error occurred: {str(e)}"
        app.logger.error(error_message)  # Log the error
        return render_template('error.html', error_message=error_message), 500

@app.route('/expressInterest', methods=['POST'])
def express_interest():
    try:
        if request.method == 'POST':
            user_id = session.get('user_id')
            trip_id = request.form.get('trip_id')

            if user_id and trip_id:
                trip = ProposedTrip.query.filter_by(trip_id=trip_id).first()

                if trip:
                    existing_interest = Interest.query.filter_by(
                        user_id=trip.user_id,
                        expressing_user_id=user_id,
                        trip_id=trip_id
                    ).first()

                    if not existing_interest:
                        # Update the ExpressInterest table
                        express_interest_record = Interest(
                            user_id=trip.user_id,  # Set user_id to the user_id of the trip creator
                            expressing_user_id=user_id,  # Set expressing_user_id to the current user_id
                            trip_id=trip_id
                        )
                        db.session.add(express_interest_record)
                        db.session.commit()

                        # Update the interest count in the ProposedTrip table
                        trip.interest_count = Interest.query.filter_by(trip_id=trip_id).count()
                        db.session.commit()

                        # Fetch details of the user expressing interest
                        expressing_user = User.query.filter_by(user_id=user_id).first()

                        return make_response(jsonify({
                            'message': f'{expressing_user.username} ({expressing_user.user_id}) expressed interest in the trip!',
                        }), 200)
                    else:
                        return make_response(jsonify({'error': 'You have already expressed interest in this trip.'}),
                                             409)
                else:
                    return make_response(jsonify({'error': 'Trip not found.'}), 404)

        return make_response(jsonify({'error': 'Invalid request.'}), 400)

    except SQLAlchemyError as db_error:
        # Handle SQLAlchemy database-related errors
        error_message = f"Database error: {str(db_error)}"
        app.logger.error(error_message)  # Log the error
        return make_response(jsonify({'error': error_message}), 500)
    except Exception as e:
        # Handle other general exceptions
        error_message = f"An unexpected error occurred: {str(e)}"
        app.logger.error(error_message)  # Log the error
        return make_response(jsonify({'error': error_message}), 500)

@app.route('/proposedTripDetails', methods=['GET', 'POST'])
def proposed_tripsDetails():
    try:
        user_id = session.get('user_id')
        trip_id = session.get('proposed_trip_id')

        if not user_id or not trip_id:
            return "Error: User ID or Trip ID not found in the session."

        proposed_trip = {
            'user_id': user_id,
            'trip_id': trip_id,
            'location': session.get('proposed_location'),
            'date': session.get('proposed_date'),
            'weather': session.get('proposed_weather')
        }

        if request.method == 'POST':
            # Express interest
            new_interest = Interest(user_id=user_id, trip_id=trip_id)
            db.session.add(new_interest)
            db.session.commit()

            return redirect(url_for('runIndex'))

        return render_template('proposedTripDetails.html', proposed_trip=proposed_trip)

    except SQLAlchemyError as db_error:
        # Handle SQLAlchemy database-related errors
        error_message = f"Database error: {str(db_error)}"
        app.logger.error(error_message)  # Log the error
        return "An unexpected error occurred. Please try again later."

    except Exception as e:
        # Handle other general exceptions
        error_message = f"An unexpected error occurred: {str(e)}"
        app.logger.error(error_message)  # Log the error
        return "An unexpected error occurred. Please try again later."

@app.route('/userProposedTrips', methods=['GET'])
def user_proposed_trips():
    try:
        user_id = session.get('user_id')

        if not user_id:
            raise ValueError("User ID not found in the session.")

        # Fetch all proposed trips for the current user
        proposed_trips = ProposedTrip.query.filter_by(user_id=user_id).all()

        return render_template('allProposedTrips.html', proposed_trips=proposed_trips)

    except ValueError as value_error:
        # Handle specific error: User ID not found in the session
        error_message = str(value_error)
        app.logger.warning(error_message)  # Log the warning
        return render_template('error.html', error_message=error_message), 400

    except SQLAlchemyError as db_error:
        # Handle SQLAlchemy database-related errors
        error_message = f"Database error: {str(db_error)}"
        app.logger.error(error_message)  # Log the error
        return render_template('error.html', error_message=error_message), 500

    except Exception as e:
        # Handle other general exceptions
        error_message = f"An unexpected error occurred: {str(e)}"
        app.logger.error(error_message)  # Log the error
        return render_template('error.html', error_message=error_message), 500

@app.route('/updateTrip/<trip_id>', methods=['PUT', 'POST'])
def update_trip_api(trip_id):
    try:
        # Fetch the trip
        trip = ProposedTrip.query.filter_by(trip_id=trip_id).first()

        if not trip:
            return jsonify({'error': 'Trip not found.'}), 404

        if request.method == 'POST':
            # Handle the update logic
            new_location = request.form.get('location')
            new_date = request.form.get('date')

            # Update the trip details
            trip.location = new_location
            trip.date = new_date

            # Fetch new weather information based on the updated location and date
            base_url = f'https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{new_location}/{new_date}/{new_date}?unitGroup=metric&key=P26NNPL4J95PEE2W5RCGSLPYR&contentType=json'
            resp = requests.get(base_url)

            resp.raise_for_status()  # Raise an HTTPError for bad responses

            weather_data = resp.json().get('days', [])
            weather_info = []

            for day in weather_data:
                date = day.get('datetime')
                avg_temp = day.get('temp', 0)
                condition = day.get('conditions')
                max_temp = day.get('tempmax', 0)
                min_temp = day.get('tempmin', 0)
                weather_info.append({
                    'date': date,
                    'avg_temp': avg_temp,
                    'condition': condition,
                    'max_temp': max_temp,
                    'min_temp': min_temp
                })

            # Update the weather information for the trip
            trip.weather = json.dumps(weather_info)

            # Commit the changes to the database
            db.session.commit()

            return jsonify({'message': 'Trip updated successfully.'}), 200

    except SQLAlchemyError as db_error:
        # Handle SQLAlchemy database-related errors
        error_message = f"Database error: {str(db_error)}"
        app.logger.error(error_message)  # Log the error
        return jsonify({'error': error_message}), 500

    except requests.RequestException as req_error:
        # Handle HTTP request-related errors
        error_message = f"Error fetching weather data: {str(req_error)}"
        app.logger.error(error_message)  # Log the error
        return jsonify({'error': error_message}), 500

    except Exception as e:
        # Handle other general exceptions
        error_message = f"An unexpected error occurred: {str(e)}"
        app.logger.error(error_message)  # Log the error
        return jsonify({'error': error_message}), 500

    return jsonify({'error': 'Invalid request method.'}), 400


@app.route('/deleteTrip/<trip_id>', methods=['DELETE'])
def delete_trip_api(trip_id):
    try:
        # Fetch the proposed trip from the database based on trip_id
        trip = ProposedTrip.query.filter_by(trip_id=trip_id).first()

        if not trip:
            return jsonify({'error': 'Trip not found.'}), 404

        # Delete the trip from the database
        db.session.delete(trip)
        db.session.commit()

        return jsonify({'message': 'Trip deleted successfully.'}), 200

    except SQLAlchemyError as db_error:
        # Handle SQLAlchemy database-related errors
        error_message = f"Database error: {str(db_error)}"
        app.logger.error(error_message)  # Log the error
        return jsonify({'error': error_message}), 500

    except Exception as e:
        # Handle other general exceptions
        error_message = f"An unexpected error occurred: {str(e)}"
        app.logger.error(error_message)  # Log the error
        return jsonify({'error': error_message}), 500


@app.route('/patchTrip/<trip_id>', methods=['PATCH'])
def patch_trip_api(trip_id):
    try:
        # Fetch the proposed trip from the database based on trip_id
        trip = ProposedTrip.query.filter_by(trip_id=trip_id).first()

        if not trip:
            return jsonify({'error': 'Trip not found.'}), 404

        if request.method == 'PATCH':
            try:
                # Get the data from the request JSON
                data = request.json
                app.logger.info(f"Received PATCH request for trip_id: {trip_id}, data: {data}")

                # Ensure 'location' and 'date' are provided
                if 'location' not in data or 'date' not in data:
                    return jsonify({'error': 'Both "location" and "date" must be provided for the update.'}), 400

                # Update the trip details
                trip.location = data['location']
                trip.date = data['date']

                # Fetch new weather information based on the updated location and date
                base_url = f'https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{trip.location}/{trip.date}/{trip.date}?unitGroup=metric&key=QGUAVPUXXDGPPHV2XEW6DDTGV&contentType=json'
                resp = requests.get(base_url)

                if resp.status_code == 200:
                    weather_data = resp.json().get('days', [])
                    weather_info = []

                    for day in weather_data:
                        date = day.get('datetime')
                        avg_temp = day.get('temp', 0)
                        condition = day.get('conditions')
                        max_temp = day.get('tempmax', 0)
                        min_temp = day.get('tempmin', 0)
                        weather_info.append({
                            'date': date,
                            'avg_temp': avg_temp,
                            'condition': condition,
                            'max_temp': max_temp,
                            'min_temp': min_temp
                        })

                    # Update the weather information for the trip
                    trip.weather = json.dumps(weather_info)

                    # Commit the changes to the database
                    db.session.commit()

                    app.logger.info(f"Trip patched successfully for trip_id: {trip_id}")
                    return jsonify({'message': 'Trip patched successfully.', 'weather_info': weather_info}), 200
                else:
                    app.logger.error(f"Error fetching weather data for trip_id {trip_id}: {resp.status_code}")
                    return jsonify({'error': f'Error fetching weather data: {resp.status_code}'}), 500

            except Exception as e:
                return jsonify({'error': str(e)}), 500

        return jsonify({'error': 'Invalid request method.'}), 400

    except SQLAlchemyError as db_error:
        # Handle SQLAlchemy database-related errors
        error_message = f"Database error: {str(db_error)}"
        app.logger.error(error_message)  # Log the error
        return jsonify({'error': error_message}), 500

    except Exception as e:
        # Handle other general exceptions
        error_message = f"An unexpected error occurred: {str(e)}"
        app.logger.error(error_message)  # Log the error
        return jsonify({'error': error_message}), 500

@app.route('/tripInterests/<trip_id>', methods=['GET'])
def trip_interests(trip_id):
    try:
        # Fetch the proposed trip from the database based on trip_id
        proposed_trip = ProposedTrip.query.filter_by(trip_id=trip_id).first()

        if not proposed_trip:
            return "Error: Proposed Trip not found."

        # Fetch the user IDs interested in the trip
        interests = Interest.query.filter_by(trip_id=trip_id).all()

        return render_template('tripInterests.html', proposed_trip=proposed_trip, interests=interests,
                               fetch_user_by_id=fetch_user_by_id)

    except SQLAlchemyError as db_error:
        # Handle SQLAlchemy database-related errors
        error_message = f"Database error: {str(db_error)}"
        app.logger.error(error_message)  # Log the error
        return render_template('error.html', error_message=error_message), 500

    except Exception as e:
        # Handle other general exceptions
        error_message = f"An unexpected error occurred: {str(e)}"
        app.logger.error(error_message)  # Log the error
        return render_template('error.html', error_message=error_message), 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))


@app.route('/queryOutput', methods=['POST'])
def weather():
    try:
        if request.method == 'POST':
            location = request.form['location']
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            base_url = f'https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{location}/{start_date}/{end_date}?unitGroup=metric&key=QGUAVPUXXDGPPHV2XEW6DDTGV&contentType=json'
            resp = requests.get(base_url)

            if resp.status_code == 200:
                data = resp.json().get('days', [])
                if data:
                    weather_data = []
                    for day in data:
                        date = day.get('datetime')
                        avg_temp = day.get('temp', 0)
                        condition = day.get('conditions')
                        max_temp = day.get('tempmax', 0)
                        min_temp = day.get('tempmin', 0)
                        weather_data.append({
                            'date': date,
                            'avg_temp': avg_temp,
                            'condition': condition,
                            'max_temp': max_temp,
                            'min_temp': min_temp
                        })

                    return render_template('queryOutput.html', location=location, start_date=start_date,
                                           end_date=end_date,
                                           weather_data=weather_data)
                else:
                    return f"No timeline data available for {location} in the specified date range."
            else:
                return f"Error: {resp.status_code}"

    except SQLAlchemyError as db_error:
        # Handle SQLAlchemy database-related errors
        error_message = f"Database error: {str(db_error)}"
        app.logger.error(error_message)  # Log the error
        return render_template('error.html', error_message=error_message), 500

    except Exception as e:
        # Handle other general exceptions
        error_message = f"An unexpected error occurred: {str(e)}"
        app.logger.error(error_message)  # Log the error
        return render_template('error.html', error_message=error_message), 500

@app.route('/pastTrips', methods=['GET'])
def past_trips():
    try:



        # Fetch all trips with dates earlier than the current date
        today = datetime.today().strftime('%Y-%m-%d')

        #queries the database to fetch all trips that occurred before today.
        past_trips = ProposedTrip.query.filter(ProposedTrip.date < today).all()

        return render_template('pastTrips.html', past_trips=past_trips)

    except SQLAlchemyError as db_error:
        # Handle SQLAlchemy database-related errors
        error_message = f"Database error: {str(db_error)}"
        app.logger.error(error_message)  # Log the error
        return render_template('error.html', error_message=error_message), 500
    except Exception as e:
        # Handle other general exceptions
        error_message = f"An unexpected error occurred: {str(e)}"
        app.logger.error(error_message)  # Log the error
        return render_template('error.html', error_message=error_message), 500

@app.route('/presentTrips', methods=['GET'])
def present_trips():
    try:
        # This Fetches all trips with dates on or after the current date
        today = datetime.today().strftime('%Y-%m-%d')
        present_trips = ProposedTrip.query.filter(ProposedTrip.date >= today).all()

        return render_template('presentTrips.html', present_trips=present_trips)

    except SQLAlchemyError as db_error:
        # Handle SQLAlchemy database-related errors
        error_message = f"Database error: {str(db_error)}"
        app.logger.error(error_message)  # Log the error
        return render_template('error.html', error_message=error_message), 500
    except Exception as e:
        # Handle other general exceptions
        error_message = f"An unexpected error occurred: {str(e)}"
        app.logger.error(error_message)  # Log the error
        return render_template('error.html', error_message=error_message), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)