from locust import HttpUser, between, task

class MyAppUser(HttpUser):
    wait_time = between(5, 15)

    @task
    def register_user(self):
        # Adjusted assertion for a successful registration (status code 200)
        response = self.client.post('/registerPage', data={
            'username': 'ronaldo',
            'password': 'ronaldo1'
        })
        assert response.status_code == 200

    @task
    def login_user(self):
        # Adjusted assertion for a successful login (status code 200)
        response = self.client.post('/loginpage', data={
            'username': 'ackom',
            'password': 'ackom1'
        })
        assert response.status_code == 200

    @task
    def perform_query(self):
        response = self.client.post('/query', data={
            'search_location': 'lagos'
        })
        assert response.status_code == 200

    @task
    def propose_trip(self):
        self.client.get('/proposedTrips')

    def on_start(self):
        # Perform any setup actions before the user starts making requests
        pass