from app.models import Organization


def test_organization_code_repo_url_field_exists(interface_with_organization):
    """Test that Organization model has code_repo_url field"""
    org = interface_with_organization.db.query(Organization).first()

    # Should be able to access the field (will be None initially)
    assert hasattr(org, "code_repo_url")
    assert org.code_repo_url is None


def test_organization_code_repo_exempt_field_exists(interface_with_organization):
    """Test that Organization model has code_repo_exempt field"""
    org = interface_with_organization.db.query(Organization).first()

    # Should be able to access the field (will default to False)
    assert hasattr(org, "code_repo_exempt")
    assert org.code_repo_exempt is False


def test_create_organization_with_code_repo_url(interface):
    """Test creating an organization with a code repository URL"""
    org = Organization(
        id="gsa-test",
        name="GSA",
        slug="gsa",
        organization_type="Federal Government",
        code_repo_url="https://github.com/GSA",
    )
    interface.db.add(org)
    interface.db.commit()

    retrieved_org = interface.db.query(Organization).filter_by(id="gsa-test").first()
    assert retrieved_org.code_repo_url == "https://github.com/GSA"
    assert retrieved_org.code_repo_exempt is False


def test_create_organization_with_code_repo_exempt(interface):
    """Test creating an organization marked as exempt"""
    org = Organization(
        id="exempt-test",
        name="Exempt Agency",
        slug="exempt-agency",
        organization_type="Federal Government",
        code_repo_exempt=True,
    )
    interface.db.add(org)
    interface.db.commit()

    retrieved_org = interface.db.query(Organization).filter_by(id="exempt-test").first()
    assert retrieved_org.code_repo_url is None
    assert retrieved_org.code_repo_exempt is True


def test_update_organization_code_repo_url(interface_with_organization):
    """Test updating an organization's code repository URL"""
    org = interface_with_organization.db.query(Organization).first()
    original_id = org.id

    org.code_repo_url = "https://github.com/GSA"
    interface_with_organization.db.commit()

    updated_org = (
        interface_with_organization.db.query(Organization)
        .filter_by(id=original_id)
        .first()
    )
    assert updated_org.code_repo_url == "https://github.com/GSA"


def test_update_organization_code_repo_exempt(interface_with_organization):
    """Test updating an organization's exemption status"""
    org = interface_with_organization.db.query(Organization).first()
    original_id = org.id

    org.code_repo_exempt = True
    interface_with_organization.db.commit()

    updated_org = (
        interface_with_organization.db.query(Organization)
        .filter_by(id=original_id)
        .first()
    )
    assert updated_org.code_repo_exempt is True
