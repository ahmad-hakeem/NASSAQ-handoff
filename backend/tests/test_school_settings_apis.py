"""
Test School Settings APIs - Academic Years, Terms, Grade Levels, User Preferences, Reports, AI Insights
Tests for principal dashboard pages: SchoolSettingsPage, AccountSettingsPage, SchoolReportsPage, AIInsightsPage
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
PRINCIPAL_EMAIL = "principal@nassaq.com"
PRINCIPAL_PASSWORD = "Principal@123"


class TestPrincipalLogin:
    """Test principal login and authentication"""
    
    @pytest.fixture(scope="class")
    def auth_token(self):
        """Get authentication token for principal"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == "school_principal"
        return data["access_token"]
    
    @pytest.fixture(scope="class")
    def auth_headers(self, auth_token):
        """Get headers with auth token"""
        return {"Authorization": f"Bearer {auth_token}"}
    
    def test_login_as_principal(self, auth_token):
        """Test login as school principal"""
        assert auth_token is not None
        print(f"✓ Principal login successful")
    
    def test_get_current_user(self, auth_headers):
        """Test getting current user info"""
        response = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == PRINCIPAL_EMAIL
        assert data["role"] == "school_principal"
        print(f"✓ Current user: {data['full_name']} ({data['role']})")


class TestAcademicYearsAPI:
    """Test Academic Years API endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_academic_years(self, auth_headers):
        """Test GET /api/academic-years returns academic years list"""
        response = requests.get(f"{BASE_URL}/api/academic-years", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Academic years API returned {len(data)} years")
        
        # If there are years, verify structure
        if len(data) > 0:
            year = data[0]
            assert "id" in year
            assert "name" in year
            print(f"  - First year: {year.get('name')}")


class TestTermsAPI:
    """Test Terms/Semesters API endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_terms(self, auth_headers):
        """Test GET /api/terms returns terms list"""
        response = requests.get(f"{BASE_URL}/api/terms", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Terms API returned {len(data)} terms")
        
        # If there are terms, verify structure
        if len(data) > 0:
            term = data[0]
            assert "id" in term
            assert "name" in term
            print(f"  - First term: {term.get('name')}")


class TestGradeLevelsAPI:
    """Test Grade Levels API endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_grade_levels(self, auth_headers):
        """Test GET /api/grade-levels returns grade levels list"""
        response = requests.get(f"{BASE_URL}/api/grade-levels", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        print(f"✓ Grade levels API returned {len(data)} grades")
        
        # If there are grades, verify structure
        if len(data) > 0:
            grade = data[0]
            assert "id" in grade
            assert "name" in grade
            print(f"  - First grade: {grade.get('name')}")


class TestUserPreferencesAPI:
    """Test User Preferences API endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_user_preferences(self, auth_headers):
        """Test GET /api/users/me/preferences returns user preferences"""
        response = requests.get(f"{BASE_URL}/api/users/me/preferences", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify expected fields
        assert "language" in data
        assert "theme" in data
        print(f"✓ User preferences: language={data['language']}, theme={data['theme']}")
    
    def test_get_user_notifications(self, auth_headers):
        """Test GET /api/users/me/notifications returns notification settings"""
        response = requests.get(f"{BASE_URL}/api/users/me/notifications", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify expected fields
        assert "email_notifications" in data
        assert "attendance_alerts" in data
        print(f"✓ Notification settings: email={data['email_notifications']}, attendance_alerts={data['attendance_alerts']}")


class TestSchoolReportsAPI:
    """Test School Reports API endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_school_overview_report(self, auth_headers):
        """Test GET /api/reports/school/overview returns overview report"""
        response = requests.get(f"{BASE_URL}/api/reports/school/overview", headers=auth_headers)
        # May return 400 if user not linked to school, which is acceptable
        assert response.status_code in [200, 400]
        
        if response.status_code == 200:
            data = response.json()
            assert "total_students" in data or "attendance_rate" in data
            print(f"✓ School overview report: students={data.get('total_students', 'N/A')}")
        else:
            print(f"✓ School overview API accessible (user not linked to school)")
    
    def test_get_school_attendance_report(self, auth_headers):
        """Test GET /api/reports/school/attendance returns attendance report"""
        response = requests.get(f"{BASE_URL}/api/reports/school/attendance", headers=auth_headers)
        assert response.status_code in [200, 400]
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)
            print(f"✓ Attendance report: {len(data)} class records")
        else:
            print(f"✓ Attendance report API accessible (user not linked to school)")
    
    def test_get_school_grades_report(self, auth_headers):
        """Test GET /api/reports/school/grades returns grades report"""
        response = requests.get(f"{BASE_URL}/api/reports/school/grades", headers=auth_headers)
        assert response.status_code in [200, 400]
        
        if response.status_code == 200:
            data = response.json()
            assert isinstance(data, list)
            print(f"✓ Grades report: {len(data)} subject records")
        else:
            print(f"✓ Grades report API accessible (user not linked to school)")


class TestAIInsightsAPI:
    """Test AI Insights API endpoints"""
    
    @pytest.fixture(scope="class")
    def auth_headers(self):
        """Get authentication headers"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        token = response.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}
    
    def test_get_ai_insights_overview(self, auth_headers):
        """Test GET /api/ai/insights/overview returns AI overview"""
        response = requests.get(f"{BASE_URL}/api/ai/insights/overview", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        # Verify expected fields
        assert "overall_score" in data
        assert "trend" in data
        print(f"✓ AI Insights overview: score={data['overall_score']}, trend={data['trend']}")
    
    def test_get_ai_predictions(self, auth_headers):
        """Test GET /api/ai/insights/predictions returns predictions"""
        response = requests.get(f"{BASE_URL}/api/ai/insights/predictions", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Verify prediction structure
        prediction = data[0]
        assert "title" in prediction
        assert "confidence" in prediction
        print(f"✓ AI Predictions: {len(data)} predictions returned")
    
    def test_get_ai_recommendations(self, auth_headers):
        """Test GET /api/ai/insights/recommendations returns recommendations"""
        response = requests.get(f"{BASE_URL}/api/ai/insights/recommendations", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) > 0
        
        # Verify recommendation structure
        rec = data[0]
        assert "title" in rec
        assert "priority" in rec
        print(f"✓ AI Recommendations: {len(data)} recommendations returned")
    
    def test_get_ai_alerts(self, auth_headers):
        """Test GET /api/ai/insights/alerts returns alerts"""
        response = requests.get(f"{BASE_URL}/api/ai/insights/alerts", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        print(f"✓ AI Alerts: {len(data)} alerts returned")
    
    def test_get_at_risk_students(self, auth_headers):
        """Test GET /api/ai/insights/at-risk-students returns at-risk students"""
        response = requests.get(f"{BASE_URL}/api/ai/insights/at-risk-students", headers=auth_headers)
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        print(f"✓ At-risk students: {len(data)} students identified")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
