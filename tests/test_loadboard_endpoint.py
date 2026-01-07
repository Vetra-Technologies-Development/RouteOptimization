"""
Tests for LoadBoard Network endpoints.
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import status

# Import the app - check if it's in app/main.py or main.py
try:
    from app.main import app
except ImportError:
    try:
        from main import app
    except ImportError:
        # If both fail, create a test app
        from fastapi import FastAPI
        from app.routers import loadboard
        app = FastAPI()
        app.include_router(loadboard.router)

client = TestClient(app)


# Sample XML data for testing
SAMPLE_XML_POST_LOADS = """<LBNLoadPostings>
  <PostingAccount>
    <UserName>testuser</UserName>
    <Password>testpass</Password>
    <ContactName>John Doe</ContactName>
    <ContactPhone>555-1234</ContactPhone>
    <ContactEmail>john@example.com</ContactEmail>
    <CompanyName>Test Trucking Co</CompanyName>
    <UserID>12345</UserID>
    <mcNumber>MC123456</mcNumber>
    <dotNumber>DOT123456</dotNumber>
  </PostingAccount>
  <PostLoads>
    <load>
      <tracking-number>TRACK001</tracking-number>
      <origin>
        <city>New York</city>
        <state>NY</state>
        <postcode>10001</postcode>
        <latitude>40.7128</latitude>
        <longitude>-74.0060</longitude>
        <date-start>
          <year>2024</year>
          <month>1</month>
          <day>15</day>
          <hour>8</hour>
          <minute>0</minute>
        </date-start>
      </origin>
      <destination>
        <city>Los Angeles</city>
        <state>CA</state>
        <postcode>90001</postcode>
        <latitude>34.0522</latitude>
        <longitude>-118.2437</longitude>
        <date-start>
          <year>2024</year>
          <month>1</month>
          <day>18</day>
          <hour>10</hour>
          <minute>0</minute>
        </date-start>
      </destination>
      <equipment>
        <dryvan/>
      </equipment>
      <loadsize fullload="true">
        <length>53</length>
        <width>102</width>
        <height>110</height>
        <weight>45000</weight>
      </loadsize>
      <load-count>1</load-count>
      <stops>0</stops>
      <distance>2790</distance>
      <rate>2500.00</rate>
      <comment>Fragile cargo - handle with care</comment>
    </load>
  </PostLoads>
</LBNLoadPostings>"""

SAMPLE_XML_REMOVE_LOADS = """<LBNLoadPostings>
  <PostingAccount>
    <UserName>testuser</UserName>
    <UserID>12345</UserID>
  </PostingAccount>
  <RemoveLoads>
    <load>
      <tracking-number>TRACK001</tracking-number>
    </load>
  </RemoveLoads>
</LBNLoadPostings>"""

MINIMAL_XML = """<LBNLoadPostings>
  <PostingAccount>
    <UserName>testuser</UserName>
    <UserID>12345</UserID>
  </PostingAccount>
  <PostLoads>
    <load>
      <tracking-number>TRACK001</tracking-number>
      <origin>
        <city>New York</city>
        <state>NY</state>
      </origin>
      <destination>
        <city>Los Angeles</city>
        <state>CA</state>
      </destination>
    </load>
  </PostLoads>
</LBNLoadPostings>"""


class TestPostLoadsEndpoint:
    """Tests for POST /loadboard/post_loads endpoint."""

    @patch('app.routers.loadboard.is_supabase_enabled')
    @patch('app.routers.loadboard.get_loadboard_service')
    def test_post_loads_success(self, mock_get_service, mock_is_enabled):
        """Test successful posting of loads."""
        # Setup mocks
        mock_is_enabled.return_value = True
        mock_service = Mock()
        mock_service.process_xml_request.return_value = ("Successfully posted", 1)
        mock_get_service.return_value = mock_service

        # Make request
        response = client.post(
            "/loadboard/post_loads",
            json={"xml": SAMPLE_XML_POST_LOADS}
        )

        # Assertions
        assert response.status_code == status.HTTP_200_OK
        assert "Successfully posted" in response.text
        mock_service.process_xml_request.assert_called_once()
        assert SAMPLE_XML_POST_LOADS in mock_service.process_xml_request.call_args[0]

    @patch('app.routers.loadboard.is_supabase_enabled')
    def test_post_loads_supabase_not_configured(self, mock_is_enabled):
        """Test error when Supabase is not configured."""
        # Setup mock
        mock_is_enabled.return_value = False

        # Make request
        response = client.post(
            "/loadboard/post_loads",
            json={"xml": SAMPLE_XML_POST_LOADS}
        )

        # Assertions
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "Supabase is not configured" in response.json()["detail"]

    @patch('app.routers.loadboard.is_supabase_enabled')
    @patch('app.routers.loadboard.get_loadboard_service')
    def test_post_loads_minimal_xml(self, mock_get_service, mock_is_enabled):
        """Test posting with minimal XML (only required fields)."""
        # Setup mocks
        mock_is_enabled.return_value = True
        mock_service = Mock()
        mock_service.process_xml_request.return_value = ("Successfully posted", 1)
        mock_get_service.return_value = mock_service

        # Make request
        response = client.post(
            "/loadboard/post_loads",
            json={"xml": MINIMAL_XML}
        )

        # Assertions
        assert response.status_code == status.HTTP_200_OK
        mock_service.process_xml_request.assert_called_once()

    @patch('app.routers.loadboard.is_supabase_enabled')
    @patch('app.routers.loadboard.get_loadboard_service')
    def test_post_loads_no_loads_found(self, mock_get_service, mock_is_enabled):
        """Test when no loads are found in XML."""
        # Setup mocks
        mock_is_enabled.return_value = True
        mock_service = Mock()
        mock_service.process_xml_request.return_value = ("Data format incorrect", 0)
        mock_get_service.return_value = mock_service

        # Make request
        response = client.post(
            "/loadboard/post_loads",
            json={"xml": MINIMAL_XML}
        )

        # Assertions
        assert response.status_code == status.HTTP_200_OK
        assert "Data format incorrect" in response.text

    @patch('app.routers.loadboard.is_supabase_enabled')
    @patch('app.routers.loadboard.get_loadboard_service')
    def test_post_loads_service_error(self, mock_get_service, mock_is_enabled):
        """Test handling of service errors."""
        # Setup mocks
        mock_is_enabled.return_value = True
        mock_service = Mock()
        mock_service.process_xml_request.side_effect = Exception("Database connection failed")
        mock_get_service.return_value = mock_service

        # Make request
        response = client.post(
            "/loadboard/post_loads",
            json={"xml": SAMPLE_XML_POST_LOADS}
        )

        # Assertions
        assert response.status_code == status.HTTP_200_OK
        assert "Error" in response.text

    def test_post_loads_invalid_json(self):
        """Test with invalid JSON body."""
        response = client.post(
            "/loadboard/post_loads",
            json={"invalid": "field"}
        )

        # Should return validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_post_loads_missing_xml_field(self):
        """Test with missing xml field."""
        response = client.post(
            "/loadboard/post_loads",
            json={}
        )

        # Should return validation error
        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    @patch('app.routers.loadboard.is_supabase_enabled')
    @patch('app.routers.loadboard.get_loadboard_service')
    def test_post_loads_invalid_xml(self, mock_get_service, mock_is_enabled):
        """Test with invalid XML content."""
        # Setup mocks
        mock_is_enabled.return_value = True
        mock_service = Mock()
        mock_service.process_xml_request.return_value = ("Data invalid: Invalid XML format", 0)
        mock_get_service.return_value = mock_service

        # Make request with invalid XML
        response = client.post(
            "/loadboard/post_loads",
            json={"xml": "<invalid>xml</invalid>"}
        )

        # Assertions
        assert response.status_code == status.HTTP_200_OK
        assert "Data invalid" in response.text or "Error" in response.text


class TestRemoveLoadsEndpoint:
    """Tests for POST /loadboard/remove_loads endpoint."""

    @patch('app.routers.loadboard.is_supabase_enabled')
    @patch('app.routers.loadboard.get_loadboard_service')
    def test_remove_loads_success(self, mock_get_service, mock_is_enabled):
        """Test successful removal of loads."""
        # Setup mocks
        mock_is_enabled.return_value = True
        mock_service = Mock()
        mock_service.process_xml_request.return_value = ("Successfully posted", 1)
        mock_get_service.return_value = mock_service

        # Make request
        response = client.post(
            "/loadboard/remove_loads",
            json={"xml": SAMPLE_XML_REMOVE_LOADS}
        )

        # Assertions
        assert response.status_code == status.HTTP_200_OK
        assert "Successfully posted" in response.text
        mock_service.process_xml_request.assert_called_once()

    @patch('app.routers.loadboard.is_supabase_enabled')
    def test_remove_loads_supabase_not_configured(self, mock_is_enabled):
        """Test error when Supabase is not configured."""
        # Setup mock
        mock_is_enabled.return_value = False

        # Make request
        response = client.post(
            "/loadboard/remove_loads",
            json={"xml": SAMPLE_XML_REMOVE_LOADS}
        )

        # Assertions
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "Supabase is not configured" in response.json()["detail"]

    @patch('app.routers.loadboard.is_supabase_enabled')
    @patch('app.routers.loadboard.get_loadboard_service')
    def test_remove_loads_no_loads_found(self, mock_get_service, mock_is_enabled):
        """Test when no loads are found to remove."""
        # Setup mocks
        mock_is_enabled.return_value = True
        mock_service = Mock()
        mock_service.process_xml_request.return_value = ("Data format incorrect", 0)
        mock_get_service.return_value = mock_service

        # Make request
        response = client.post(
            "/loadboard/remove_loads",
            json={"xml": SAMPLE_XML_REMOVE_LOADS}
        )

        # Assertions
        assert response.status_code == status.HTTP_200_OK
        assert "Data format incorrect" in response.text


class TestXMLValidation:
    """Tests for XML validation and parsing."""

    @patch('app.routers.loadboard.is_supabase_enabled')
    @patch('app.routers.loadboard.get_loadboard_service')
    def test_multiple_loads(self, mock_get_service, mock_is_enabled):
        """Test posting multiple loads in one request."""
        # Setup mocks
        mock_is_enabled.return_value = True
        mock_service = Mock()
        mock_service.process_xml_request.return_value = ("Successfully posted", 2)
        mock_get_service.return_value = mock_service

        # XML with multiple loads
        multi_load_xml = """<LBNLoadPostings>
          <PostingAccount>
            <UserName>testuser</UserName>
            <UserID>12345</UserID>
          </PostingAccount>
          <PostLoads>
            <load>
              <tracking-number>TRACK001</tracking-number>
              <origin><city>New York</city><state>NY</state></origin>
              <destination><city>Los Angeles</city><state>CA</state></destination>
            </load>
            <load>
              <tracking-number>TRACK002</tracking-number>
              <origin><city>Chicago</city><state>IL</state></origin>
              <destination><city>Houston</city><state>TX</state></destination>
            </load>
          </PostLoads>
        </LBNLoadPostings>"""

        # Make request
        response = client.post(
            "/loadboard/post_loads",
            json={"xml": multi_load_xml}
        )

        # Assertions
        assert response.status_code == status.HTTP_200_OK
        assert "Successfully posted" in response.text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

