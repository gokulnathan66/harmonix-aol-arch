"""
Tests for manifest.yaml validation
"""

from utils.validators import validate_manifest


def test_template_manifest():
    """Test that the template manifest.yaml is valid"""
    result = validate_manifest("manifest.yaml")

    # Print issues for debugging
    if not result.valid:
        for issue in result.issues:
            print(f"{issue}")

    assert result.valid, "Template manifest.yaml should be valid"

    # Should have minimal warnings
    assert len(result.warnings) <= 2, "Template should have minimal warnings"
