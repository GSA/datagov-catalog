import os

from app import create_app

# cloud.gov sets VCAP_APPLICATION; "production" gives https in url_for()
application = create_app(
    config_name="production" if os.getenv("VCAP_APPLICATION") else "local"
)
