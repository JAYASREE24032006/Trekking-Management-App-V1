import unittest
from app import app
from models import db, User, Trek, Booking
from werkzeug.security import generate_password_hash

class TrekoraIntegrationTest(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'  # Use in-memory DB for tests
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()
        
        with app.app_context():
            db.create_all()
            # Clear existing tables to ensure a clean state
            Booking.query.delete()
            Trek.query.delete()
            User.query.delete()
            db.session.commit()

            # Bootstrap Admin
            admin_pw = generate_password_hash('admin123')
            admin = User(
                name='System Admin',
                email='admin@trekora.com',
                contact='9999999999',
                role='admin',
                password_hash=admin_pw,
                status='approved'
            )
            db.session.add(admin)
            db.session.commit()

    def tearDown(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()

    def login(self, email, password):
        return self.client.post('/login', data=dict(
            email=email,
            password=password
        ), follow_redirects=True)

    def logout(self):
        return self.client.get('/logout', follow_redirects=True)

    def test_full_workflow(self):
        # 1. Verify Admin Login
        response = self.login('admin@trekora.com', 'admin123')
        self.assertIn(b'System Admin', response.data)
        self.assertIn(b'Admin Dashboard', response.data)
        self.logout()

        # 2. Register Trek Staff
        response = self.client.post('/register', data=dict(
            name='Vikas Singh',
            email='vikas@mail.com',
            contact='9876543210',
            role='staff',
            password='password123',
            confirm_password='password123'
        ), follow_redirects=True)
        self.assertIn(b'Registration successful', response.data)

        # 3. Register Trekker User
        response = self.client.post('/register', data=dict(
            name='Amit Sharma',
            email='amit@mail.com',
            contact='9123456780',
            role='user',
            password='password123',
            confirm_password='password123'
        ), follow_redirects=True)
        self.assertIn(b'Registration successful', response.data)

        # 4. Verify Staff Pending Warning
        response = self.login('vikas@mail.com', 'password123')
        self.assertIn(b'pending approval by the Admin', response.data)

        # 5. Admin Approves Staff
        self.login('admin@trekora.com', 'admin123')
        
        # Approve Vikas (ID 2 because Admin is ID 1)
        response = self.client.get('/admin/staff/approve/2', follow_redirects=True)
        self.assertIn(b'is now approved', response.data)

        # 6. Admin Adds Treks
        # Trek 1: Everest Base Camp (Approved -> Closed initially)
        response = self.client.post('/admin/trek/new', data=dict(
            name='Everest Base Camp',
            location='Nepal',
            difficulty='Hard',
            duration=12,
            slots=20,
            start_date='2026-08-20',
            end_date='2026-08-31',
            staff_id=2,
            status='Approved',
            description='A challenging hike to the base of the world\'s tallest peak.'
        ), follow_redirects=True)
        self.assertIn(b'New trek route created successfully', response.data)

        # Trek 2: Roopkund Trek (Open)
        response = self.client.post('/admin/trek/new', data=dict(
            name='Roopkund Trek',
            location='Uttarakhand',
            difficulty='Moderate',
            duration=7,
            slots=15,
            start_date='2026-09-10',
            end_date='2026-09-17',
            staff_id=2,
            status='Open',
            description='A scenic moderate hike to the mystery lake.'
        ), follow_redirects=True)
        self.assertIn(b'New trek route created successfully', response.data)
        self.logout()

        # 7. Staff Logs in and Opens Everest Base Camp Trek
        self.login('vikas@mail.com', 'password123')
        response = self.client.get('/staff', follow_redirects=True)
        self.assertIn(b'Everest Base Camp', response.data)
        self.assertIn(b'Roopkund Trek', response.data)

        # Open Everest Base Camp
        response = self.client.post('/staff/trek/update/1', data=dict(
            slots=20,
            status='Open'
        ), follow_redirects=True)
        self.assertIn(b'Trek settings updated successfully', response.data)
        self.logout()

        # 8. Hiker Logs in, Filters, and Books Trek
        self.login('amit@mail.com', 'password123')
        
        # Check filter endpoints
        response = self.client.get('/user?tab=browse&difficulty=Hard', follow_redirects=True)
        self.assertIn(b'Everest Base Camp', response.data)
        self.assertNotIn(b'Roopkund Trek', response.data)

        # Book Everest Base Camp (Trek ID 1)
        response = self.client.get('/trek/1/book', follow_redirects=True)
        self.assertIn(b'booked successfully', response.data)
        
        # Check active bookings
        response = self.client.get('/user?tab=bookings', follow_redirects=True)
        self.assertIn(b'Everest Base Camp', response.data)
        self.logout()

        # 9. Staff Starts and Completes the Trek
        self.login('vikas@mail.com', 'password123')
        # View specific trek management
        response = self.client.get('/staff?manage=1', follow_redirects=True)
        self.assertIn(b'Amit Sharma', response.data)

        # Start Trek
        response = self.client.get('/staff/trek/start/1', follow_redirects=True)
        self.assertIn(b'marked as Started', response.data)

        # Complete Trek
        response = self.client.get('/staff/trek/complete/1', follow_redirects=True)
        self.assertIn(b'marked as Completed', response.data)
        self.logout()

        # 10. Hiker Verifies History
        self.login('amit@mail.com', 'password123')
        response = self.client.get('/user?tab=history', follow_redirects=True)
        self.assertIn(b'Completed', response.data)
        self.assertIn(b'Everest Base Camp', response.data)
        self.logout()

        # 11. Verify REST APIs
        response = self.client.get('/api/treks')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Everest Base Camp', response.data)
        
        response = self.client.get('/api/bookings')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Amit Sharma', response.data)

if __name__ == '__main__':
    unittest.main()
