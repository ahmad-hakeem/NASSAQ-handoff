"""
NASSAQ Communication Center & Reports API Tests
Tests for:
- Communication Center: stats, messages, templates, audience, scheduled messages
- Reports: overview, attendance, grades, behavior, top-classes
"""
import pytest
import requests
import os
from datetime import datetime, timedelta

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

# Test credentials
PRINCIPAL_EMAIL = "principal1@nassaq.com"
PRINCIPAL_PASSWORD = "Principal@123"


class TestAuthentication:
    """Authentication tests"""
    
    def test_login_as_principal(self):
        """Test login as school principal"""
        response = requests.post(f"{BASE_URL}/api/auth/login", json={
            "email": PRINCIPAL_EMAIL,
            "password": PRINCIPAL_PASSWORD
        })
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "access_token" in data, "No access_token in response"
        assert data.get("user", {}).get("role") == "school_principal", f"Wrong role: {data.get('user', {}).get('role')}"
        print(f"✓ Login successful as principal")
        return data["access_token"]


@pytest.fixture(scope="module")
def auth_token():
    """Get authentication token for tests"""
    response = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": PRINCIPAL_EMAIL,
        "password": PRINCIPAL_PASSWORD
    })
    if response.status_code != 200:
        pytest.skip(f"Authentication failed: {response.text}")
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    """Get headers with auth token"""
    return {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }


# ============ COMMUNICATION CENTER TESTS ============

class TestCommunicationStats:
    """Communication statistics endpoint tests"""
    
    def test_get_communication_stats(self, auth_headers):
        """Test GET /communication/stats"""
        response = requests.get(f"{BASE_URL}/api/communication/stats", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "sent" in data, "Missing 'sent' in stats"
        assert "scheduled" in data, "Missing 'scheduled' in stats"
        assert "templates" in data, "Missing 'templates' in stats"
        
        # Verify data types
        assert isinstance(data["sent"], int), "sent should be int"
        assert isinstance(data["scheduled"], int), "scheduled should be int"
        assert isinstance(data["templates"], int), "templates should be int"
        
        print(f"✓ Communication stats: sent={data['sent']}, scheduled={data['scheduled']}, templates={data['templates']}")


class TestCommunicationMessages:
    """Communication messages CRUD tests"""
    
    def test_get_messages_list(self, auth_headers):
        """Test GET /communication - list messages"""
        response = requests.get(f"{BASE_URL}/api/communication?limit=100", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "messages" in data, "Missing 'messages' in response"
        assert "total" in data, "Missing 'total' in response"
        assert isinstance(data["messages"], list), "messages should be a list"
        
        print(f"✓ Messages list: {len(data['messages'])} messages, total={data['total']}")
    
    def test_send_message_immediately(self, auth_headers):
        """Test POST /communication - send message now"""
        message_data = {
            "title": "TEST_رسالة اختبار فورية",
            "content": "هذه رسالة اختبار للإرسال الفوري من نظام الاختبار",
            "audience": "teachers",
            "channels": ["in_app"]
        }
        
        response = requests.post(f"{BASE_URL}/api/communication", json=message_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "id" in data, "Missing 'id' in response"
        assert data.get("status") == "sent", f"Expected status 'sent', got '{data.get('status')}'"
        assert "recipient_count" in data, "Missing 'recipient_count' in response"
        
        print(f"✓ Message sent: id={data['id']}, recipients={data['recipient_count']}")
        return data["id"]
    
    def test_schedule_message(self, auth_headers):
        """Test POST /communication - schedule message"""
        # Schedule for tomorrow
        scheduled_time = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT10:00:00")
        
        message_data = {
            "title": "TEST_رسالة مجدولة",
            "content": "هذه رسالة مجدولة للإرسال لاحقاً",
            "audience": "students",
            "channels": ["in_app"],
            "scheduled_at": scheduled_time
        }
        
        response = requests.post(f"{BASE_URL}/api/communication", json=message_data, headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "id" in data, "Missing 'id' in response"
        assert data.get("status") == "scheduled", f"Expected status 'scheduled', got '{data.get('status')}'"
        
        print(f"✓ Message scheduled: id={data['id']}, scheduled_at={scheduled_time}")
        return data["id"]
    
    def test_get_received_messages(self, auth_headers):
        """Test GET /communication/received"""
        response = requests.get(f"{BASE_URL}/api/communication/received", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert "messages" in data, "Missing 'messages' in response"
        assert isinstance(data["messages"], list), "messages should be a list"
        
        print(f"✓ Received messages: {len(data['messages'])} messages")


class TestCommunicationTemplates:
    """Communication templates tests"""
    
    def test_get_templates(self, auth_headers):
        """Test GET /communication/templates"""
        response = requests.get(f"{BASE_URL}/api/communication/templates", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Templates should be a list"
        
        if len(data) > 0:
            template = data[0]
            assert "id" in template, "Template missing 'id'"
            assert "name" in template or "name_en" in template, "Template missing name"
            assert "content_template" in template, "Template missing 'content_template'"
            print(f"✓ Templates: {len(data)} templates found")
            print(f"  First template: {template.get('name', template.get('name_en'))}")
        else:
            print(f"✓ Templates: No templates found (default templates should be returned)")


class TestCommunicationAudience:
    """Communication audience tests"""
    
    def test_get_audience_stats(self, auth_headers):
        """Test GET /communication/audience"""
        response = requests.get(f"{BASE_URL}/api/communication/audience", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Audience should be a list"
        assert len(data) >= 4, f"Expected at least 4 audience groups, got {len(data)}"
        
        # Verify audience groups
        audience_ids = [a["id"] for a in data]
        assert "all" in audience_ids, "Missing 'all' audience"
        assert "teachers" in audience_ids, "Missing 'teachers' audience"
        assert "students" in audience_ids, "Missing 'students' audience"
        assert "parents" in audience_ids, "Missing 'parents' audience"
        
        for group in data:
            assert "count" in group, f"Missing 'count' in audience group {group.get('id')}"
            assert isinstance(group["count"], int), f"count should be int for {group.get('id')}"
            print(f"  {group['id']}: {group['count']} users")
        
        print(f"✓ Audience groups: {len(data)} groups")


class TestScheduledMessages:
    """Scheduled messages management tests"""
    
    def test_update_scheduled_message(self, auth_headers):
        """Test PUT /communication/{id} - update scheduled message"""
        # First create a scheduled message
        scheduled_time = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%dT10:00:00")
        
        create_response = requests.post(f"{BASE_URL}/api/communication", json={
            "title": "TEST_رسالة للتعديل",
            "content": "محتوى أصلي",
            "audience": "all",
            "channels": ["in_app"],
            "scheduled_at": scheduled_time
        }, headers=auth_headers)
        
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        message_id = create_response.json()["id"]
        
        # Update the message
        update_response = requests.put(f"{BASE_URL}/api/communication/{message_id}", json={
            "title": "TEST_رسالة معدلة",
            "content": "محتوى معدل",
            "audience": "teachers"
        }, headers=auth_headers)
        
        assert update_response.status_code == 200, f"Update failed: {update_response.text}"
        print(f"✓ Scheduled message updated: {message_id}")
        
        # Cleanup - delete the message
        requests.delete(f"{BASE_URL}/api/communication/{message_id}", headers=auth_headers)
    
    def test_send_scheduled_message_now(self, auth_headers):
        """Test POST /communication/{id}/send-now"""
        # First create a scheduled message
        scheduled_time = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%dT10:00:00")
        
        create_response = requests.post(f"{BASE_URL}/api/communication", json={
            "title": "TEST_رسالة للإرسال الفوري",
            "content": "سيتم إرسالها الآن",
            "audience": "teachers",
            "channels": ["in_app"],
            "scheduled_at": scheduled_time
        }, headers=auth_headers)
        
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        message_id = create_response.json()["id"]
        
        # Send now
        send_response = requests.post(f"{BASE_URL}/api/communication/{message_id}/send-now", headers=auth_headers)
        assert send_response.status_code == 200, f"Send now failed: {send_response.text}"
        
        data = send_response.json()
        assert data.get("success") == True, "Expected success=True"
        
        print(f"✓ Scheduled message sent immediately: {message_id}")
    
    def test_delete_scheduled_message(self, auth_headers):
        """Test DELETE /communication/{id}"""
        # First create a scheduled message
        scheduled_time = (datetime.now() + timedelta(days=4)).strftime("%Y-%m-%dT10:00:00")
        
        create_response = requests.post(f"{BASE_URL}/api/communication", json={
            "title": "TEST_رسالة للحذف",
            "content": "سيتم حذفها",
            "audience": "all",
            "channels": ["in_app"],
            "scheduled_at": scheduled_time
        }, headers=auth_headers)
        
        assert create_response.status_code == 200, f"Create failed: {create_response.text}"
        message_id = create_response.json()["id"]
        
        # Delete
        delete_response = requests.delete(f"{BASE_URL}/api/communication/{message_id}", headers=auth_headers)
        assert delete_response.status_code == 200, f"Delete failed: {delete_response.text}"
        
        print(f"✓ Scheduled message deleted: {message_id}")


# ============ REPORTS TESTS ============

class TestReportsOverview:
    """Reports overview endpoint tests"""
    
    def test_get_school_overview(self, auth_headers):
        """Test GET /reports/school/overview"""
        response = requests.get(f"{BASE_URL}/api/reports/school/overview?period=current_term", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "total_students" in data, "Missing 'total_students'"
        assert "total_teachers" in data, "Missing 'total_teachers'"
        assert "total_classes" in data, "Missing 'total_classes'"
        assert "attendance_rate" in data, "Missing 'attendance_rate'"
        assert "attendance" in data, "Missing 'attendance' object"
        
        # Verify attendance object
        attendance = data["attendance"]
        assert "present" in attendance, "Missing 'present' in attendance"
        assert "absent" in attendance, "Missing 'absent' in attendance"
        assert "late" in attendance, "Missing 'late' in attendance"
        
        print(f"✓ Overview report: students={data['total_students']}, teachers={data['total_teachers']}, classes={data['total_classes']}")
        print(f"  Attendance rate: {data['attendance_rate']}%")


class TestReportsAttendance:
    """Reports attendance endpoint tests"""
    
    def test_get_attendance_report(self, auth_headers):
        """Test GET /reports/school/attendance"""
        response = requests.get(f"{BASE_URL}/api/reports/school/attendance?period=current_term", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Attendance report should be a list"
        
        if len(data) > 0:
            row = data[0]
            assert "class" in row or "class_en" in row, "Missing class name"
            assert "present" in row, "Missing 'present'"
            assert "absent" in row, "Missing 'absent'"
            assert "late" in row, "Missing 'late'"
            assert "rate" in row, "Missing 'rate'"
            
            print(f"✓ Attendance report: {len(data)} classes")
            for r in data[:3]:
                print(f"  {r.get('class', r.get('class_en'))}: {r['rate']}% attendance")
        else:
            print(f"✓ Attendance report: No data (empty list)")


class TestReportsGrades:
    """Reports grades endpoint tests"""
    
    def test_get_grades_report(self, auth_headers):
        """Test GET /reports/school/grades"""
        response = requests.get(f"{BASE_URL}/api/reports/school/grades?period=current_term", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Grades report should be a list"
        
        if len(data) > 0:
            row = data[0]
            assert "subject" in row or "subject_en" in row, "Missing subject name"
            assert "avg" in row, "Missing 'avg'"
            assert "highest" in row, "Missing 'highest'"
            assert "lowest" in row, "Missing 'lowest'"
            assert "pass_rate" in row, "Missing 'pass_rate'"
            
            print(f"✓ Grades report: {len(data)} subjects")
            for r in data[:3]:
                print(f"  {r.get('subject', r.get('subject_en'))}: avg={r['avg']}%, pass_rate={r['pass_rate']}%")
        else:
            print(f"✓ Grades report: No data (empty list)")


class TestReportsBehavior:
    """Reports behavior endpoint tests"""
    
    def test_get_behavior_report(self, auth_headers):
        """Test GET /reports/school/behavior"""
        response = requests.get(f"{BASE_URL}/api/reports/school/behavior?period=current_term", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        # Verify response structure
        assert "stats" in data, "Missing 'stats'"
        assert "recent_notes" in data, "Missing 'recent_notes'"
        
        stats = data["stats"]
        assert "positive" in stats, "Missing 'positive' in stats"
        assert "negative" in stats, "Missing 'negative' in stats"
        assert "warning" in stats, "Missing 'warning' in stats"
        assert "total" in stats, "Missing 'total' in stats"
        
        print(f"✓ Behavior report: positive={stats['positive']}, negative={stats['negative']}, warnings={stats['warning']}")
        print(f"  Recent notes: {len(data['recent_notes'])} notes")
        
        # Verify recent notes structure
        if len(data["recent_notes"]) > 0:
            note = data["recent_notes"][0]
            assert "student_name" in note, "Missing 'student_name' in note"
            assert "note" in note, "Missing 'note' in note"
            assert "type" in note, "Missing 'type' in note"


class TestReportsTopClasses:
    """Reports top classes endpoint tests"""
    
    def test_get_top_classes(self, auth_headers):
        """Test GET /reports/school/top-classes"""
        response = requests.get(f"{BASE_URL}/api/reports/school/top-classes", headers=auth_headers)
        assert response.status_code == 200, f"Failed: {response.text}"
        data = response.json()
        
        assert isinstance(data, list), "Top classes should be a list"
        
        if len(data) > 0:
            cls = data[0]
            assert "class_id" in cls, "Missing 'class_id'"
            assert "class_name" in cls, "Missing 'class_name'"
            assert "score" in cls, "Missing 'score'"
            assert "rank_reason" in cls, "Missing 'rank_reason'"
            
            print(f"✓ Top classes: {len(data)} classes")
            for i, c in enumerate(data[:3], 1):
                print(f"  #{i} {c['class_name']}: score={c['score']}")
        else:
            print(f"✓ Top classes: No data (empty list)")


# ============ CLEANUP ============

class TestCleanup:
    """Cleanup test data"""
    
    def test_cleanup_test_messages(self, auth_headers):
        """Clean up TEST_ prefixed messages"""
        # Get all messages
        response = requests.get(f"{BASE_URL}/api/communication?limit=100", headers=auth_headers)
        if response.status_code == 200:
            messages = response.json().get("messages", [])
            deleted = 0
            for msg in messages:
                if msg.get("title", "").startswith("TEST_"):
                    del_response = requests.delete(f"{BASE_URL}/api/communication/{msg['id']}", headers=auth_headers)
                    if del_response.status_code == 200:
                        deleted += 1
            print(f"✓ Cleanup: deleted {deleted} test messages")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
