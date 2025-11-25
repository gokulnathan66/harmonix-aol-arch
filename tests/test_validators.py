"""
Tests for validators module
"""
import pytest
import yaml
import tempfile
import os
from utils.validators import (
    ManifestValidator,
    ConfigValidator,
    ValidationSeverity,
    validate_manifest,
    validate_config
)


class TestManifestValidator:
    """Test manifest validation"""
    
    def test_valid_manifest(self):
        """Test validation of a valid manifest"""
        manifest = {
            'kind': 'AOLService',
            'apiVersion': 'v1',
            'metadata': {
                'name': 'test-service',
                'version': '1.0.0',
                'labels': {'role': 'service'}
            },
            'spec': {
                'endpoints': {
                    'grpc': '50051',
                    'health': '50200',
                    'metrics': '8080'
                },
                'dependencies': [
                    {'service': 'aol-core', 'optional': False}
                ]
            }
        }
        
        validator = ManifestValidator()
        result = validator.validate(manifest)
        
        assert result.valid
        assert len(result.errors) == 0
    
    def test_missing_required_field(self):
        """Test validation fails when required field is missing"""
        manifest = {
            'kind': 'AOLService',
            'apiVersion': 'v1',
            # Missing 'metadata'
            'spec': {
                'endpoints': {
                    'grpc': '50051',
                    'health': '50200'
                }
            }
        }
        
        validator = ManifestValidator()
        result = validator.validate(manifest)
        
        assert not result.valid
        assert len(result.errors) > 0
        assert any('metadata' in issue.path for issue in result.errors)
    
    def test_invalid_kind(self):
        """Test validation fails with invalid kind"""
        manifest = {
            'kind': 'InvalidKind',
            'apiVersion': 'v1',
            'metadata': {
                'name': 'test-service',
                'version': '1.0.0'
            },
            'spec': {
                'endpoints': {
                    'grpc': '50051',
                    'health': '50200'
                }
            }
        }
        
        validator = ManifestValidator()
        result = validator.validate(manifest)
        
        assert not result.valid
        assert any('kind' in issue.path for issue in result.errors)
    
    def test_invalid_port_range(self):
        """Test validation catches invalid port numbers"""
        manifest = {
            'kind': 'AOLService',
            'apiVersion': 'v1',
            'metadata': {
                'name': 'test-service',
                'version': '1.0.0'
            },
            'spec': {
                'endpoints': {
                    'grpc': '99999',  # Invalid port
                    'health': '50200'
                }
            }
        }
        
        validator = ManifestValidator()
        result = validator.validate(manifest)
        
        assert not result.valid
        assert any('port' in issue.message.lower() for issue in result.errors)
    
    def test_validate_file(self):
        """Test validation from file"""
        manifest = {
            'kind': 'AOLAgent',
            'apiVersion': 'v1',
            'metadata': {
                'name': 'test-agent',
                'version': '1.0.0'
            },
            'spec': {
                'endpoints': {
                    'grpc': '50051',
                    'health': '50200'
                }
            }
        }
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(manifest, f)
            temp_path = f.name
        
        try:
            validator = ManifestValidator()
            result = validator.validate_file(temp_path)
            assert result.valid
        finally:
            os.unlink(temp_path)
    
    def test_file_not_found(self):
        """Test validation handles missing file"""
        validator = ManifestValidator()
        result = validator.validate_file('/nonexistent/path/manifest.yaml')
        
        assert not result.valid
        assert len(result.errors) > 0


class TestConfigValidator:
    """Test config validation"""
    
    def test_valid_config(self):
        """Test validation of valid config"""
        config = {
            'service': {
                'name': 'test-service',
                'kind': 'AOLService'
            },
            'dataClient': {
                'enabled': True,
                'aolCoreEndpoint': 'aol-core:50051'
            },
            'resilience': {
                'circuitBreaker': {
                    'enabled': True,
                    'failureThreshold': 5
                }
            }
        }
        
        validator = ConfigValidator()
        result = validator.validate(config)
        
        assert result.valid
    
    def test_missing_aol_core_endpoint(self):
        """Test warning when data client enabled without endpoint"""
        config = {
            'dataClient': {
                'enabled': True
                # Missing aolCoreEndpoint
            }
        }
        
        validator = ConfigValidator()
        result = validator.validate(config)
        
        # Should be valid but have warnings
        assert result.valid
        assert len(result.warnings) > 0
    
    def test_invalid_circuit_breaker_threshold(self):
        """Test warning for invalid circuit breaker threshold"""
        config = {
            'resilience': {
                'circuitBreaker': {
                    'enabled': True,
                    'failureThreshold': 0  # Should be at least 1
                }
            }
        }
        
        validator = ConfigValidator()
        result = validator.validate(config)
        
        assert result.valid  # Warning, not error
        assert len(result.warnings) > 0


class TestUtilityFunctions:
    """Test utility functions"""
    
    def test_validate_manifest_function(self):
        """Test validate_manifest convenience function"""
        manifest = {
            'kind': 'AOLTool',
            'apiVersion': 'v1',
            'metadata': {
                'name': 'test-tool',
                'version': '1.0.0'
            },
            'spec': {
                'endpoints': {
                    'grpc': '50051',
                    'health': '50200'
                }
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(manifest, f)
            temp_path = f.name
        
        try:
            result = validate_manifest(temp_path)
            assert result.valid
        finally:
            os.unlink(temp_path)
    
    def test_validate_config_function(self):
        """Test validate_config convenience function"""
        config = {
            'service': {
                'name': 'test-service'
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            temp_path = f.name
        
        try:
            result = validate_config(temp_path)
            assert result.valid
        finally:
            os.unlink(temp_path)
