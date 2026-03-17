"""
Test Dashboard Stats API with Global Filters
Tests for NASSAQ Platform Admin Dashboard filters:
- Scope filter (all/single/multi)
- City filter
- Region filter
- School type filter
- Time window filter
- Status filter (active/suspended/setup/pending)
"""

import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
ADMIN_EMAIL = "info@nassaqapp.com"
ADMIN_PASSWORD = "NassaqAdmin2026!##$$HBJ"


class TestDashboardFilters:
    """Dashboard Stats API filter tests"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        self.token = data["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
        self.user = data["user"]
    
    def test_login_as_platform_admin(self):
        """Test 1: Login as Platform Admin"""
        assert self.user["email"] == ADMIN_EMAIL
        assert self.user["role"] == "platform_admin"
        assert self.user["full_name"] == "مدير المنصة"
        print(f"✓ Login successful - User: {self.user['full_name']}")
    
    def test_dashboard_stats_no_filters(self):
        """Test 2: Get dashboard stats without filters"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Verify expected fields exist
        assert "total_schools" in data
        assert "total_students" in data
        assert "total_teachers" in data
        assert "active_schools" in data
        assert "suspended_schools" in data
        assert "pending_schools" in data
        
        # Verify data values match expected (210 total schools)
        assert data["total_schools"] == 210, f"Expected 210 schools, got {data['total_schools']}"
        print(f"✓ Total schools: {data['total_schools']}")
        print(f"✓ Active schools: {data['active_schools']}")
        print(f"✓ Suspended schools: {data['suspended_schools']}")
        print(f"✓ Pending schools: {data['pending_schools']}")
    
    def test_filter_by_status_active(self):
        """Test 3: Filter by status=active - should show 141 schools"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats?status=active",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # When filtering by active status, total_schools should be 141
        assert data["total_schools"] == 141, f"Expected 141 active schools, got {data['total_schools']}"
        print(f"✓ Active schools filter: {data['total_schools']} schools")
        print(f"✓ Students in active schools: {data['total_students']}")
        print(f"✓ Teachers in active schools: {data['total_teachers']}")
    
    def test_filter_by_status_suspended(self):
        """Test 4: Filter by status=suspended - should show 1 school"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats?status=suspended",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_schools"] == 1, f"Expected 1 suspended school, got {data['total_schools']}"
        print(f"✓ Suspended schools filter: {data['total_schools']} school")
    
    def test_filter_by_status_pending(self):
        """Test 5: Filter by status=pending - should show 67 schools"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats?status=pending",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_schools"] == 67, f"Expected 67 pending schools, got {data['total_schools']}"
        print(f"✓ Pending schools filter: {data['total_schools']} schools")
    
    def test_filter_by_status_setup(self):
        """Test 6: Filter by status=setup - should show 1 school"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats?status=setup",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_schools"] == 1, f"Expected 1 setup school, got {data['total_schools']}"
        print(f"✓ Setup schools filter: {data['total_schools']} school")
    
    def test_filter_by_city_riyadh(self):
        """Test 7: Filter by city=الرياض - should show 23 schools"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats?city=الرياض",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert data["total_schools"] == 23, f"Expected 23 schools in الرياض, got {data['total_schools']}"
        print(f"✓ الرياض city filter: {data['total_schools']} schools")
        print(f"✓ Students in الرياض: {data['total_students']}")
        print(f"✓ Teachers in الرياض: {data['total_teachers']}")
    
    def test_filter_by_time_window_today(self):
        """Test 8: Filter by time_window=today"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats?time_window=today",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Time window affects operations count, not school count
        assert "total_operations" in data
        print(f"✓ Today time window: {data['total_operations']} operations")
    
    def test_filter_by_time_window_week(self):
        """Test 9: Filter by time_window=week"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats?time_window=week",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "total_operations" in data
        print(f"✓ Week time window: {data['total_operations']} operations")
    
    def test_filter_by_time_window_month(self):
        """Test 10: Filter by time_window=month"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats?time_window=month",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        assert "total_operations" in data
        print(f"✓ Month time window: {data['total_operations']} operations")
    
    def test_combined_filters_city_and_status(self):
        """Test 11: Combined filters - city=الرياض AND status=active"""
        response = requests.get(
            f"{BASE_URL}/api/dashboard/stats?city=الرياض&status=active",
            headers=self.headers
        )
        assert response.status_code == 200
        data = response.json()
        
        # Should show only active schools in الرياض (14 schools)
        assert data["total_schools"] == 14, f"Expected 14 active schools in الرياض, got {data['total_schools']}"
        print(f"✓ Combined filter (الرياض + active): {data['total_schools']} schools")
    
    def test_data_changes_with_filters(self):
        """Test 12: Verify data actually changes when filters are applied"""
        # Get all stats
        response_all = requests.get(
            f"{BASE_URL}/api/dashboard/stats",
            headers=self.headers
        )
        data_all = response_all.json()
        
        # Get active only
        response_active = requests.get(
            f"{BASE_URL}/api/dashboard/stats?status=active",
            headers=self.headers
        )
        data_active = response_active.json()
        
        # Verify numbers are different
        assert data_all["total_schools"] != data_active["total_schools"], \
            "Total schools should differ between all and active filter"
        assert data_all["total_schools"] == 210
        assert data_active["total_schools"] == 141
        
        print(f"✓ Data changes verified:")
        print(f"  - All schools: {data_all['total_schools']}")
        print(f"  - Active schools: {data_active['total_schools']}")
        print(f"  - Difference: {data_all['total_schools'] - data_active['total_schools']} schools")


class TestSchoolsAPI:
    """Schools API tests for filter verification"""
    
    @pytest.fixture(autouse=True)
    def setup(self):
        """Login and get auth token"""
        response = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}
        )
        assert response.status_code == 200
        data = response.json()
        self.token = data["access_token"]
        self.headers = {"Authorization": f"Bearer {self.token}"}
    
    def test_get_all_schools(self):
        """Test: Get all schools list"""
        response = requests.get(
            f"{BASE_URL}/api/schools",
            headers=self.headers
        )
        assert response.status_code == 200
        schools = response.json()
        
        assert len(schools) == 210, f"Expected 210 schools, got {len(schools)}"
        print(f"✓ Total schools in list: {len(schools)}")
    
    def test_get_active_schools(self):
        """Test: Get active schools only"""
        response = requests.get(
            f"{BASE_URL}/api/schools?status=active",
            headers=self.headers
        )
        assert response.status_code == 200
        schools = response.json()
        
        assert len(schools) == 141, f"Expected 141 active schools, got {len(schools)}"
        print(f"✓ Active schools in list: {len(schools)}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
