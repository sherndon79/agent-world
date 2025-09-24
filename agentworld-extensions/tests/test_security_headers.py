"""
Security tests for HTTP response headers.

Tests that security headers are properly included in all HTTP responses
to prevent various web-based attacks.
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock
from io import BytesIO

from agent_world_http import WorldHTTPHandler


class MockHTTPServer:
    """Mock HTTP server for testing."""
    pass


class TestSecurityHeaders:
    """Test suite for HTTP security headers."""

    def setup_method(self):
        """Set up test environment with mock HTTP handler."""
        # Create a mock API interface
        self.mock_api_interface = Mock()
        self.mock_api_interface.get_port.return_value = 8900
        self.mock_api_interface.is_running.return_value = True
        self.mock_api_interface.get_stats.return_value = {'requests': 0, 'errors': 0}

        # Create HTTP handler class bound to mock API
        self.handler_class = WorldHTTPHandler.create_handler_class(
            self.mock_api_interface, 'test-extension'
        )

        # Mock the HTTP request/response infrastructure
        self.mock_wfile = BytesIO()
        self.mock_rfile = BytesIO(b'{"test": "data"}')
        self.mock_request = MagicMock()
        self.mock_request.makefile.return_value = self.mock_rfile

        # Create handler instance with mocked socket infrastructure
        with patch('socket.socket'):
            self.handler = self.handler_class(
                request=self.mock_request,
                client_address=('127.0.0.1', 12345),
                server=MockHTTPServer()
            )

        # Mock the wfile and rfile
        self.handler.wfile = self.mock_wfile
        self.handler.rfile = self.mock_rfile

        # Track sent headers
        self.sent_headers = {}
        self.response_code = None

        def mock_send_header(name, value):
            self.sent_headers[name] = value

        def mock_send_response(code):
            self.response_code = code

        def mock_end_headers():
            pass

        self.handler.send_header = mock_send_header
        self.handler.send_response = mock_send_response
        self.handler.end_headers = mock_end_headers

    def test_json_response_security_headers(self):
        """Test that JSON responses include all security headers."""
        test_data = {'success': True, 'message': 'test'}

        self.handler._send_json_response(test_data)

        # Verify security headers are present
        assert 'Content-Security-Policy' in self.sent_headers
        assert 'X-Content-Type-Options' in self.sent_headers
        assert 'X-Frame-Options' in self.sent_headers
        assert 'X-XSS-Protection' in self.sent_headers
        assert 'Referrer-Policy' in self.sent_headers
        assert 'Permissions-Policy' in self.sent_headers

        # Verify header values
        assert self.sent_headers['Content-Security-Policy'].startswith("default-src 'self'")
        assert self.sent_headers['X-Content-Type-Options'] == 'nosniff'
        assert self.sent_headers['X-Frame-Options'] == 'DENY'
        assert self.sent_headers['X-XSS-Protection'] == '1; mode=block'
        assert 'strict-origin-when-cross-origin' in self.sent_headers['Referrer-Policy']

        # Verify response code
        assert self.response_code == 200

        # Verify content type
        assert self.sent_headers['Content-Type'] == 'application/json'

    def test_raw_response_security_headers(self):
        """Test that raw responses include security headers."""
        test_content = "# Prometheus metrics\ntest_metric 1.0"

        self.handler._send_raw_response(test_content, 'text/plain')

        # Verify security headers are present
        assert 'Content-Security-Policy' in self.sent_headers
        assert 'X-Content-Type-Options' in self.sent_headers
        assert 'X-Frame-Options' in self.sent_headers
        assert 'X-XSS-Protection' in self.sent_headers

        # Verify content type is preserved
        assert self.sent_headers['Content-Type'] == 'text/plain'

    def test_error_response_security_headers(self):
        """Test that error responses include security headers."""
        self.handler._send_error_response(404, 'Not found')

        # Verify security headers are present
        assert 'Content-Security-Policy' in self.sent_headers
        assert 'X-Content-Type-Options' in self.sent_headers
        assert 'X-Frame-Options' in self.sent_headers
        assert 'X-XSS-Protection' in self.sent_headers

        # Verify error response code
        assert self.response_code == 404

        # Verify content type
        assert self.sent_headers['Content-Type'] == 'application/json'

    def test_cors_preflight_security_headers(self):
        """Test that CORS preflight responses include security headers."""
        self.handler._send_cors_response()

        # Verify security headers are present
        assert 'Content-Security-Policy' in self.sent_headers
        assert 'X-Content-Type-Options' in self.sent_headers
        assert 'X-Frame-Options' in self.sent_headers
        assert 'X-XSS-Protection' in self.sent_headers

        # Verify CORS headers are present
        assert 'Access-Control-Allow-Origin' in self.sent_headers
        assert 'Access-Control-Allow-Methods' in self.sent_headers
        assert 'Access-Control-Allow-Headers' in self.sent_headers

        # Verify response code
        assert self.response_code == 200

    def test_unauthorized_response_headers(self):
        """Test that 401 responses include WWW-Authenticate header."""
        self.handler._send_error_response(401, 'Unauthorized')

        # Verify security headers are present
        assert 'Content-Security-Policy' in self.sent_headers
        assert 'X-Content-Type-Options' in self.sent_headers

        # Verify authentication header is present
        assert 'WWW-Authenticate' in self.sent_headers
        assert 'HMAC-SHA256' in self.sent_headers['WWW-Authenticate']
        assert 'isaac-sim' in self.sent_headers['WWW-Authenticate']

        # Verify response code
        assert self.response_code == 401

    def test_content_security_policy_details(self):
        """Test Content Security Policy header details."""
        self.handler._send_json_response({'test': 'data'})

        csp = self.sent_headers['Content-Security-Policy']

        # Verify CSP directives
        assert "default-src 'self'" in csp
        assert "script-src 'none'" in csp
        assert "object-src 'none'" in csp
        assert "frame-src 'none'" in csp

        # Should allow inline styles for basic formatting
        assert "style-src 'self' 'unsafe-inline'" in csp

        # Should allow self and data URLs for images
        assert "img-src 'self' data:" in csp

    def test_permissions_policy_restrictions(self):
        """Test Permissions Policy header restrictions."""
        self.handler._send_json_response({'test': 'data'})

        permissions_policy = self.sent_headers['Permissions-Policy']

        # Verify dangerous permissions are disabled
        assert 'geolocation=()' in permissions_policy
        assert 'microphone=()' in permissions_policy
        assert 'camera=()' in permissions_policy
        assert 'payment=()' in permissions_policy

    def test_hsts_header_when_enabled(self):
        """Test HSTS header when enabled in configuration."""
        # Mock HTTP config with HSTS enabled
        with patch('agent_world_http.HTTP_CONFIG', {
            'security_headers': {
                'enable_hsts': True,
                'hsts_max_age': 'max-age=31536000; includeSubDomains'
            }
        }):
            self.handler._send_json_response({'test': 'data'})

            # Verify HSTS header is present
            assert 'Strict-Transport-Security' in self.sent_headers
            assert 'max-age=31536000' in self.sent_headers['Strict-Transport-Security']
            assert 'includeSubDomains' in self.sent_headers['Strict-Transport-Security']

    def test_hsts_header_when_disabled(self):
        """Test HSTS header is not included when disabled."""
        # Mock HTTP config with HSTS disabled (default)
        with patch('agent_world_http.HTTP_CONFIG', {
            'security_headers': {
                'enable_hsts': False
            }
        }):
            self.handler._send_json_response({'test': 'data'})

            # Verify HSTS header is not present
            assert 'Strict-Transport-Security' not in self.sent_headers

    def test_custom_security_header_values(self):
        """Test custom security header values from configuration."""
        custom_config = {
            'security_headers': {
                'x_frame_options': 'SAMEORIGIN',
                'x_content_type_options': 'nosniff',
                'referrer_policy': 'no-referrer',
                'content_security_policy': "default-src 'none'"
            }
        }

        with patch('agent_world_http.HTTP_CONFIG', custom_config):
            self.handler._send_json_response({'test': 'data'})

            # Verify custom values are used
            assert self.sent_headers['X-Frame-Options'] == 'SAMEORIGIN'
            assert self.sent_headers['X-Content-Type-Options'] == 'nosniff'
            assert self.sent_headers['Referrer-Policy'] == 'no-referrer'
            assert self.sent_headers['Content-Security-Policy'] == "default-src 'none'"

    def test_cors_headers_preserved(self):
        """Test that CORS headers are preserved alongside security headers."""
        self.handler._send_json_response({'test': 'data'})

        # Verify both security and CORS headers are present
        assert 'Content-Security-Policy' in self.sent_headers
        assert 'Access-Control-Allow-Origin' in self.sent_headers
        assert 'Vary' in self.sent_headers

        # Verify CORS values
        assert self.sent_headers['Access-Control-Allow-Origin'] == '*'
        assert self.sent_headers['Vary'] == 'Origin'


class TestSecurityHeadersIntegration:
    """Integration tests for security headers with full request handling."""

    def test_health_endpoint_security_headers(self):
        """Test that health endpoint includes security headers."""
        # This would require setting up a full HTTP server mock
        # For now, we'll test the individual response methods
        pass

    def test_metrics_endpoint_security_headers(self):
        """Test that metrics endpoints include security headers."""
        # This would require setting up a full HTTP server mock
        pass


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
