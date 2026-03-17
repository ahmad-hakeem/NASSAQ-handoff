import requests
import sys
from datetime import datetime
import json

class NassaqAPITester:
    def __init__(self, base_url="https://school-timetable-ai.preview.emergentagent.com"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.admin_user = None

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/api/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        
        if headers:
            test_headers.update(headers)

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=10)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    response_data = response.json()
                    print(f"   Response: {json.dumps(response_data, indent=2)[:200]}...")
                except:
                    print(f"   Response: {response.text[:100]}...")
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                print(f"   Response: {response.text[:200]}...")

            return success, response.json() if response.headers.get('content-type', '').startswith('application/json') else {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_seed_admin(self):
        """Create admin user if not exists"""
        success, response = self.run_test(
            "Seed Admin User",
            "POST",
            "seed/admin",
            200
        )
        return success

    def test_login(self, email, password):
        """Test login and get token"""
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "auth/login",
            200,
            data={"email": email, "password": password}
        )
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.admin_user = response.get('user')
            print(f"   Token obtained: {self.token[:20]}...")
            return True
        return False

    def test_get_me(self):
        """Test get current user"""
        success, response = self.run_test(
            "Get Current User",
            "GET",
            "auth/me",
            200
        )
        return success

    def test_dashboard_stats(self):
        """Test dashboard stats endpoint"""
        success, response = self.run_test(
            "Dashboard Stats",
            "GET",
            "dashboard/stats",
            200
        )
        return success

    def test_get_schools(self):
        """Test get schools list"""
        success, response = self.run_test(
            "Get Schools List",
            "GET",
            "schools",
            200
        )
        return success, response

    def test_create_school(self):
        """Test create new school"""
        school_data = {
            "name": "مدرسة الاختبار",
            "name_en": "Test School",
            "code": f"TEST{datetime.now().strftime('%H%M%S')}",
            "email": f"test{datetime.now().strftime('%H%M%S')}@school.com",
            "phone": "+966501234567",
            "city": "الرياض",
            "student_capacity": 500
        }
        
        success, response = self.run_test(
            "Create School",
            "POST",
            "schools",
            200,
            data=school_data
        )
        return success, response.get('id') if success else None

    def test_hakim_chat(self):
        """Test Hakim AI assistant"""
        success, response = self.run_test(
            "Hakim Chat",
            "POST",
            "hakim/chat",
            200,
            data={
                "message": "مرحبا، كيف يمكنك مساعدتي؟",
                "context": None,
                "user_role": "platform_admin",
                "tenant_id": None
            }
        )
        return success

    def test_register_user(self):
        """Test user registration"""
        user_data = {
            "email": f"testuser{datetime.now().strftime('%H%M%S')}@test.com",
            "password": "TestPass123!",
            "full_name": "Test User",
            "full_name_en": "Test User",
            "role": "teacher",
            "phone": "+966501234567"
        }
        
        success, response = self.run_test(
            "User Registration",
            "POST",
            "auth/register",
            200,
            data=user_data
        )
        return success

def main():
    print("🚀 Starting NASSAQ API Testing...")
    print("=" * 50)
    
    # Setup
    tester = NassaqAPITester()
    
    # Test sequence
    print("\n📋 Phase 1: Authentication & Setup")
    if not tester.test_seed_admin():
        print("❌ Failed to seed admin, continuing anyway...")
    
    if not tester.test_login("admin@nassaq.sa", "Admin@123"):
        print("❌ Login failed, stopping tests")
        return 1

    print("\n📋 Phase 2: Core API Endpoints")
    tester.test_get_me()
    tester.test_dashboard_stats()
    
    schools_success, schools_data = tester.test_get_schools()
    
    print("\n📋 Phase 3: School Management")
    school_success, school_id = tester.test_create_school()
    
    print("\n📋 Phase 4: AI Assistant")
    tester.test_hakim_chat()
    
    print("\n📋 Phase 5: User Management")
    tester.test_register_user()

    # Print results
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {tester.tests_passed}/{tester.tests_run} passed")
    
    if tester.tests_passed == tester.tests_run:
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"⚠️  {tester.tests_run - tester.tests_passed} tests failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())